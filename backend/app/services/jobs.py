from __future__ import annotations

from uuid import uuid4

from arq.connections import ArqRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..db_models import Job, JobKind, JobStatus
from ..downloader.errors import InvalidUrlError
from ..downloader.urls import TargetKind, parse_target
from ..schemas import StatsOut
from ..storage import Storage


class QueueError(RuntimeError):
    """The job was stored but could not be put into the queue."""


async def enqueue_job(redis: ArqRedis, job_id: str) -> None:
    await redis.enqueue_job(
        "process_job", job_id, _job_id=f"job:{job_id}:{uuid4().hex[:8]}"
    )


async def get_job(session: AsyncSession, job_id: str) -> Job | None:
    result = await session.execute(
        select(Job).options(selectinload(Job.files)).where(Job.id == job_id)
    )
    return result.scalar_one_or_none()


async def create_job(
    session: AsyncSession,
    redis: ArqRedis,
    *,
    url: str,
    include_stories: bool,
    include_highlights: bool,
) -> Job:
    settings = get_settings()
    target = parse_target(url)

    if target.kind == TargetKind.HIGHLIGHTS:
        raise InvalidUrlError(
            "Прямые ссылки на highlights не поддерживаются. "
            "Укажите профиль и включите «Скачать highlights»."
        )

    options: dict[str, object] = {}
    if target.kind == TargetKind.POST:
        kind = JobKind.POST
    elif target.kind == TargetKind.PROFILE:
        kind = JobKind.PROFILE
        if include_highlights and not settings.highlights_available:
            raise InvalidUrlError(
                settings.highlights_reason or "Highlights недоступны"
            )
        options = {
            "include_stories": include_stories,
            "include_highlights": include_highlights,
        }
    elif target.kind == TargetKind.STORIES:
        kind = JobKind.STORIES
    else:  # pragma: no cover - parse_target only returns known kinds
        raise InvalidUrlError(f"Неподдерживаемая ссылка: {url!r}")

    job = Job(
        url=url.strip(),
        normalized_url=target.url,
        kind=kind.value,
        status=JobStatus.QUEUED.value,
        options=options,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        await enqueue_job(redis, job.id)
    except Exception as exc:
        job.status = JobStatus.FAILED.value
        job.error = f"Не удалось поставить задачу в очередь: {exc}"
        await session.commit()
        raise QueueError(job.error) from exc

    fresh = await get_job(session, job.id)
    return fresh or job


async def list_jobs(
    session: AsyncSession,
    *,
    status: JobStatus | None,
    kind: JobKind | None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    filters = []
    if status is not None:
        filters.append(Job.status == status.value)
    if kind is not None:
        filters.append(Job.kind == kind.value)

    count_statement = select(func.count()).select_from(Job)
    if filters:
        count_statement = count_statement.where(*filters)
    total = int((await session.execute(count_statement)).scalar_one())

    statement = (
        select(Job)
        .options(selectinload(Job.files))
        .order_by(Job.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if filters:
        statement = statement.where(*filters)
    jobs = list((await session.execute(statement)).scalars().all())
    return jobs, total


async def delete_job(
    session: AsyncSession, storage: Storage, job: Job
) -> None:
    storage.delete_job(job.id)
    await session.delete(job)
    await session.commit()


async def retry_job(
    session: AsyncSession, redis: ArqRedis, storage: Storage, job: Job
) -> Job:
    if job.status in (JobStatus.QUEUED.value, JobStatus.RUNNING.value):
        raise ValueError("Задача уже выполняется")

    storage.delete_job(job.id)
    job.files.clear()
    await session.flush()
    job.status = JobStatus.QUEUED.value
    job.progress = 0
    job.total_items = 0
    job.downloaded_items = 0
    job.author = None
    job.caption = None
    job.title = None
    job.error = None
    job.started_at = None
    job.finished_at = None
    await session.commit()

    try:
        await enqueue_job(redis, job.id)
    except Exception as exc:
        job.status = JobStatus.FAILED.value
        job.error = f"Не удалось поставить задачу в очередь: {exc}"
        await session.commit()
        raise QueueError(job.error) from exc

    fresh = await get_job(session, job.id)
    return fresh or job


async def get_stats(session: AsyncSession) -> StatsOut:
    rows = await session.execute(
        select(Job.status, func.count()).group_by(Job.status)
    )
    counts = {status: int(count) for status, count in rows.all()}
    total = sum(counts.values())
    return StatsOut(
        total=total,
        queued=counts.get(JobStatus.QUEUED.value, 0),
        running=counts.get(JobStatus.RUNNING.value, 0),
        success=counts.get(JobStatus.SUCCESS.value, 0),
        partial=counts.get(JobStatus.PARTIAL.value, 0),
        failed=counts.get(JobStatus.FAILED.value, 0),
    )
