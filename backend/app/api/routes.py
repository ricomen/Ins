from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, get_current_admin, verify_password
from ..config import get_settings
from ..database import get_session
from ..db_models import JobKind, JobStatus
from ..downloader.errors import InvalidUrlError
from ..schemas import (
    AppConfigOut,
    BatchError,
    BatchJobCreate,
    BatchJobOut,
    JobCreate,
    JobListOut,
    JobOut,
    LoginRequest,
    StatsOut,
    TokenResponse,
)
from ..services import jobs as job_service
from ..storage import Storage

public_router = APIRouter(prefix="/api", tags=["public"])
protected_router = APIRouter(
    prefix="/api",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@public_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@public_router.get("/config", response_model=AppConfigOut)
async def app_config() -> AppConfigOut:
    settings = get_settings()
    return AppConfigOut(
        highlights_available=settings.highlights_available,
        highlights_reason=settings.highlights_reason,
        max_batch_size=settings.max_batch_size,
        job_ttl_hours=settings.job_ttl_hours,
    )


@public_router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if not verify_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль",
        )
    return TokenResponse(access_token=create_access_token())


@protected_router.post("/jobs", response_model=JobOut, status_code=201)
async def create_job_endpoint(
    payload: JobCreate,
    request: Request,
    session: SessionDep,
) -> JobOut:
    redis = request.app.state.redis
    try:
        job = await job_service.create_job(
            session,
            redis,
            url=payload.url,
            include_stories=payload.include_stories,
            include_highlights=payload.include_highlights,
        )
    except InvalidUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except job_service.QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobOut.model_validate(job)


@protected_router.post("/jobs/batch", response_model=BatchJobOut, status_code=201)
async def create_batch_endpoint(
    payload: BatchJobCreate,
    request: Request,
    session: SessionDep,
) -> BatchJobOut:
    settings = get_settings()
    if len(payload.urls) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Максимум {settings.max_batch_size} ссылок за один раз",
        )

    redis = request.app.state.redis
    created: list[JobOut] = []
    errors: list[BatchError] = []
    for url in payload.urls:
        try:
            job = await job_service.create_job(
                session,
                redis,
                url=url,
                include_stories=payload.include_stories,
                include_highlights=payload.include_highlights,
            )
            created.append(JobOut.model_validate(job))
        except (InvalidUrlError, job_service.QueueError) as exc:
            errors.append(BatchError(url=url, error=str(exc)))

    return BatchJobOut(jobs=created, errors=errors)


@protected_router.get("/jobs", response_model=JobListOut)
async def list_jobs_endpoint(
    session: SessionDep,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    kind: JobKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListOut:
    jobs, total = await job_service.list_jobs(
        session,
        status=status_filter,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return JobListOut(
        items=[JobOut.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@protected_router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job_endpoint(
    job_id: str,
    session: SessionDep,
) -> JobOut:
    job = await job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return JobOut.model_validate(job)


@protected_router.delete("/jobs/{job_id}", status_code=204)
async def delete_job_endpoint(
    job_id: str,
    session: SessionDep,
) -> Response:
    job = await job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status == JobStatus.RUNNING.value:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить задачу, которая выполняется",
        )
    storage = Storage(get_settings().storage_dir)
    await job_service.delete_job(session, storage, job)
    return Response(status_code=204)


@protected_router.post("/jobs/{job_id}/retry", response_model=JobOut)
async def retry_job_endpoint(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> JobOut:
    job = await job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    storage = Storage(get_settings().storage_dir)
    try:
        refreshed = await job_service.retry_job(
            session, request.app.state.redis, storage, job
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except job_service.QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobOut.model_validate(refreshed)


@protected_router.get("/jobs/{job_id}/archive")
async def download_archive_endpoint(
    job_id: str,
    session: SessionDep,
) -> FileResponse:
    job = await job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not job.files:
        raise HTTPException(status_code=404, detail="В задаче нет файлов")

    storage = Storage(get_settings().storage_dir)
    files = [(item.position, item.filename, Path(item.path)) for item in job.files]
    archive = await asyncio.to_thread(storage.build_archive, job.id, files)
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=f"ins-{job.id[:8]}.zip",
    )


@protected_router.get("/jobs/{job_id}/files/{file_id}")
async def download_file_endpoint(
    job_id: str,
    file_id: str,
    session: SessionDep,
) -> FileResponse:
    job = await job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    media = next((item for item in job.files if item.id == file_id), None)
    if media is None:
        raise HTTPException(status_code=404, detail="Файл не найден")

    path = Path(media.path)
    try:
        resolved = await asyncio.to_thread(path.resolve)
        root = await asyncio.to_thread(get_settings().storage_dir.resolve)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Файл не найден") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(
        resolved,
        media_type=media.content_type or "application/octet-stream",
        filename=media.filename,
    )


@protected_router.get("/stats", response_model=StatsOut)
async def stats_endpoint(
    session: SessionDep,
) -> StatsOut:
    return await job_service.get_stats(session)
