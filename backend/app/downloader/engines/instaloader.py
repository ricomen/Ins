"""Highlights support through Instaloader.

iqsaved intentionally does not serve highlights, and Instagram requires an
authenticated session for them. This engine is therefore optional: it becomes
available only when an Instaloader session file is configured.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import instaloader

from ..errors import (
    ContentNotFoundError,
    DownloadTimeoutError,
    EngineUnavailableError,
)
from ..models import DownloadedFile, MediaItem, MediaKind, ResolvedCollection

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class HighlightsEngine:
    name = "instaloader"

    def __init__(
        self,
        *,
        login_username: str | None,
        session_file: Path | None,
        timeout: float = 60.0,
    ) -> None:
        self.login_username = login_username or None
        self.session_file = session_file
        self.timeout = timeout
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=15.0),
            follow_redirects=True,
            headers={
                "User-Agent": _BROWSER_UA,
                "Referer": "https://www.instagram.com/",
            },
        )

    @property
    def available(self) -> bool:
        return bool(
            self.login_username
            and self.session_file
            and self.session_file.is_file()
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def resolve(self, username: str) -> ResolvedCollection:
        if not self.available:
            raise EngineUnavailableError(
                "Highlights требуют сессию Instagram. Укажите "
                "INS_INSTAGRAM_USERNAME и INS_INSTAGRAM_SESSION_FILE."
            )
        return await asyncio.to_thread(self._resolve_sync, username)

    def _resolve_sync(self, username: str) -> ResolvedCollection:
        loader = self._make_loader()
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            highlights = list(profile.get_highlights())
        except instaloader.exceptions.ProfileNotExistsException as exc:
            raise ContentNotFoundError(f"Профиль @{username} не найден") from exc
        except instaloader.exceptions.LoginRequiredException as exc:
            raise EngineUnavailableError(
                "Instagram требует авторизацию для highlights. Проверьте сессию."
            ) from exc
        except instaloader.exceptions.ConnectionException as exc:
            raise EngineUnavailableError(f"Instagram недоступен: {exc}") from exc

        items: list[MediaItem] = []
        for highlight in highlights:
            try:
                highlight_items = list(highlight.get_items())
            except instaloader.exceptions.LoginRequiredException as exc:
                raise EngineUnavailableError(
                    "Сессия Instagram не даёт доступ к highlights."
                ) from exc
            except instaloader.exceptions.ConnectionException as exc:
                raise EngineUnavailableError(f"Instagram недоступен: {exc}") from exc

            for item in highlight_items:
                is_video = item.is_video
                url = item.video_url if is_video else item.url
                if not url:
                    continue
                suffix = "mp4" if is_video else "jpg"
                filename = (
                    f"{username}_highlight_{highlight.unique_id}_"
                    f"{item.mediaid}.{suffix}"
                )
                items.append(
                    MediaItem(
                        kind=MediaKind.VIDEO if is_video else MediaKind.PHOTO,
                        filename=filename,
                        download_url=url,
                        source_url=(
                            "https://www.instagram.com/stories/highlights/"
                            f"{highlight.unique_id}/"
                        ),
                        index=len(items),
                        content_type="video/mp4" if is_video else "image/jpeg",
                        engine=self.name,
                    )
                )

        if not items:
            raise ContentNotFoundError(f"У @{username} нет доступных highlights")

        return ResolvedCollection(
            title=f"Highlights @{username}",
            url=f"https://www.instagram.com/{username}/",
            author=username,
            items=items,
            engine=self.name,
            kind="highlights",
        )

    async def download(self, item: MediaItem, destination: Path) -> DownloadedFile:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f"{destination.name}.part")
        try:
            async with self._http.stream("GET", item.download_url) as response:
                if response.status_code in (401, 403, 404):
                    raise ContentNotFoundError(
                        f"Медиа недоступно (HTTP {response.status_code})"
                    )
                if response.status_code >= 400:
                    raise EngineUnavailableError(
                        f"Instagram CDN вернул HTTP {response.status_code}"
                    )
                content_type = response.headers.get("content-type")
                size = 0
                with temporary.open("wb") as file:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if not chunk:
                            continue
                        file.write(chunk)
                        size += len(chunk)
            temporary.replace(destination)
        except httpx.TimeoutException as exc:
            temporary.unlink(missing_ok=True)
            raise DownloadTimeoutError(
                f"Таймаут скачивания {item.filename}"
            ) from exc
        except httpx.HTTPError as exc:
            temporary.unlink(missing_ok=True)
            raise EngineUnavailableError(f"Ошибка скачивания: {exc}") from exc
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return DownloadedFile(
            path=str(destination),
            filename=destination.name,
            size=size,
            content_type=content_type,
        )

    def _make_loader(self) -> instaloader.Instaloader:
        if not self.login_username or not self.session_file:
            raise EngineUnavailableError("Сессия Instagram не настроена")
        loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            save_metadata=False,
            compress_json=False,
        )
        try:
            loader.load_session_from_file(
                self.login_username, str(self.session_file)
            )
        except FileNotFoundError as exc:
            raise EngineUnavailableError(
                f"Файл сессии не найден: {self.session_file}"
            ) from exc
        except instaloader.exceptions.ConnectionException as exc:
            raise EngineUnavailableError(f"Не удалось загрузить сессию: {exc}") from exc
        return loader


def highlight_id_from_url(value: str) -> str | None:
    """Best-effort extraction of a highlight id from an Instagram URL."""

    parts = [part for part in value.split("/") if part]
    if "highlights" in parts:
        index = parts.index("highlights")
        if index + 1 < len(parts):
            return parts[index + 1]
    return None
