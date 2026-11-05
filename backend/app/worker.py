from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from .config import Settings, get_settings
from .database import SessionLocal, init_db
from .db_models import Job, JobKind, JobStatus, MediaFile, utcnow
from .downloader.engines import HighlightsEngine, IqSavedEngine
from .downloader.errors import (
    DownloaderError,
    DownloadTimeoutError,
    EngineUnavailableError,
)
from .downloader.models import DownloadedFile, MediaItem
from .storage import Storage


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    await init_db()

    storage = Storage(settings.storage_dir)
    storage.ensure_root()
    ctx["settings"] = settings
    ctx["storage"] = storage
    ctx["iqsaved"] = IqSavedEngine(
        min_interval=settings.download_min_interval,
        timeout=settings.download_timeout,
        max_attempts=settings.download_attempts,
    )
    ctx["highlights"] = HighlightsEngine(
        login_username=settings.instagram_login,
        session_file=settings.instagram_session_file,
        timeout=max(settings.download_timeout, 60.0),
    )

    # A worker restart leaves running jobs orphaned. Mark them failed so they
    # can be retried from the dashboard.
    async with SessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.status == JobStatus.RUNNING.value)
        )
        for job in result.scalars():
            job.status = JobStatus.FAILED.value
            job.error = "Worker был перезапущен во время выполнения задачи"
            job.finished_at = utcnow()
        await session.commit()


async def shutdown(ctx: dict[str, Any]) -> None:
    iqsaved: IqSavedEngine | None = ctx.get("iqsaved")
    highlights: HighlightsEngine | None = ctx.get("highlights")
    if iqsaved:
        await iqsaved.close()
    if highlights:
        await highlights.close()


async def process_job(ctx: dict[str, Any], job_id: str) -> None:
    storage: Storage = ctx["storage"]
    iqsaved: IqSavedEngine = ctx["iqsaved"]
    highlights: HighlightsEngine = ctx["highlights"]

    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        if job.status not in (JobStatus.QUEUED.value, JobStatus.FAILED.value):
            return

        job.status = JobStatus.RUNNING.value
        job.started_at = utcnow()
        job.finished_at = None
        job.progress = 1
        job.error = None
        await session.commit()

        warnings: list[str] = []
        errors: list[str] = []

        try:
            items, meta, warnings = await _resolve(
                job, iqsaved, highlights, ctx["settings"]
            )
            job.total_items = len(items)
            job.author = meta.get("author")
            job.caption = meta.get("caption")
            job.title = meta.get("title")
            job.error = "; ".join(warnings) if warnings else None
            await session.commit()

            job_dir = storage.job_dir(job.id)
            job_dir.mkdir(parents=True, exist_ok=True)

            downloaded_count = 0
            for index, item in enumerate(items, start=1):
                try:
                    destination = storage.unique_path(
                        job_dir / storage.safe_filename(item.filename)
                    )
                    downloaded = await _download(item, destination, iqsaved, highlights)
                    session.add(
                        MediaFile(
                            job_id=job.id,
                            filename=destination.name,
                            path=str(destination),
                            size=downloaded.size,
                            content_type=downloaded.content_type or item.content_type,
                            kind=item.kind.value,
                            position=index - 1,
                        )
                    )
                    downloaded_count += 1
                    job.downloaded_items = downloaded_count
                    job.progress = max(
                        1, int(downloaded_count * 100 / len(items))
                    )
                    await session.commit()
                except Exception as exc:  # keep downloading the remaining items
                    errors.append(f"{item.filename}: {exc}")
                    job.error = _join_messages(warnings + errors)
                    await session.commit()

            if errors and downloaded_count == 0:
                job.status = JobStatus.FAILED.value
            elif errors or warnings:
                job.status = JobStatus.PARTIAL.value
            else:
                job.status = JobStatus.SUCCESS.value
                job.progress = 100

            job.error = _join_messages(warnings + errors)
            if job.status == JobStatus.PARTIAL.value and downloaded_count:
                job.progress = max(
                    1, int(downloaded_count * 100 / len(items))
                )
        except Exception as exc:
            await session.rollback()
            job = await session.get(Job, job_id)
            if job is not None:
                job.status = JobStatus.FAILED.value
                job.error = _join_messages(
                    [*warnings, _describe_error(exc)]
                )
        finally:
            if job is not None:
                job.finished_at = utcnow()
                if job.status == JobStatus.SUCCESS.value:
                    job.progress = 100
                await session.commit()


async def _resolve(
    job: Job,
    iqsaved: IqSavedEngine,
    highlights: HighlightsEngine,
    settings: Settings,
) -> tuple[list[MediaItem], dict[str, str | None], list[str]]:
    warnings: list[str] = []
    items: list[MediaItem] = []
    author: str | None = None
    caption: str | None = None
    title: str | None = None

    if job.kind == JobKind.POST.value:
        post = await iqsaved.resolve(job.url)
        items = list(post.items)
        author = post.author
        caption = post.caption
        title = post.shortcode
    elif job.kind == JobKind.PROFILE.value:
        include_stories = bool(job.options.get("include_stories", True))
        collection = await iqsaved.resolve_profile(
            job.url, include_stories=include_stories
        )
        items = list(collection.items)
        author = collection.author
        caption = collection.caption
        title = collection.title

        if bool(job.options.get("include_highlights", False)):
            username = collection.author
            if not username:
                warnings.append("Highlights: не удалось определить username")
            elif not highlights.available:
                warnings.append(
                    settings.highlights_reason or "Highlights недоступны"
                )
            else:
                try:
                    highlight_collection = await highlights.resolve(username)
                    items.extend(highlight_collection.items)
                except DownloaderError as exc:
                    warnings.append(f"Highlights: {exc}")
    elif job.kind == JobKind.STORIES.value:
        collection = await iqsaved.resolve_stories(job.url)
        items = list(collection.items)
        author = collection.author
        caption = collection.caption
        title = collection.title
    else:
        raise DownloaderError(f"Неподдерживаемый тип задачи: {job.kind}")

    if not items:
        raise DownloaderError(
            _join_messages(warnings) or "Нет доступных медиафайлов"
        )

    return items, {"author": author, "caption": caption, "title": title}, warnings


async def _download(
    item: MediaItem,
    destination: Path,
    iqsaved: IqSavedEngine,
    highlights: HighlightsEngine,
) -> DownloadedFile:
    last_error: EngineUnavailableError | None = None
    for attempt in range(3):
        try:
            if item.engine == "instaloader":
                return await highlights.download(item, destination)
            return await iqsaved.download(item, destination)
        except (DownloadTimeoutError, EngineUnavailableError) as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(2.0 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise EngineUnavailableError(f"Не удалось скачать {item.filename}")


def _join_messages(messages: list[str]) -> str | None:
    cleaned = [message.strip() for message in messages if message.strip()]
    if not cleaned:
        return None
    return "; ".join(cleaned)[:4000]


def _describe_error(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc).strip()
    return f"{name}: {text}" if text else name


async def cleanup(ctx: dict[str, Any]) -> None:
    settings: Settings = ctx["settings"]
    storage: Storage = ctx["storage"]
    cutoff = utcnow() - timedelta(hours=settings.job_ttl_hours)

    async with SessionLocal() as session:
        result = await session.execute(select(Job).where(Job.created_at < cutoff))
        jobs = list(result.scalars().unique())
        for job in jobs:
            storage.delete_job(job.id)
            await session.delete(job)
        await session.commit()


class WorkerSettings:
    functions = [process_job]
    cron_jobs = [cron(cleanup, minute=0)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 1
    job_timeout = 3600
    keep_result = 3600
    health_check_interval = 60
