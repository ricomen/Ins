from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
import socketio

from ..errors import (
    ContentNotFoundError,
    DownloadTimeoutError,
    EngineUnavailableError,
    InvalidUrlError,
    ProtocolError,
    RateLimitedError,
)
from ..models import (
    DownloadedFile,
    MediaItem,
    MediaKind,
    ResolvedCollection,
    ResolvedPost,
)
from ..urls import TargetKind, normalize_post_url, parse_target

IQSAVED_BASE_URL = "https://iqsaved.com"
IQSAVED_CDN_URL = "https://cdn.iqsaved.com"
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{IQSAVED_BASE_URL}/",
}
_RETRYABLE_CODES = {408, 422, 428, 429, 430, 434, 435, 436}
_NOT_FOUND_CODES = {403, 404}
_T = TypeVar("_T")


class AsyncRateLimiter:
    """Simple in-process limiter: one logical request per `min_interval` seconds."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_started = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._last_started + self.min_interval - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_started = time.monotonic()


class IqSavedEngine:
    name = "iqsaved"

    def __init__(
        self,
        *,
        base_url: str = IQSAVED_BASE_URL,
        timeout: float = 30.0,
        min_interval: float = 3.0,
        max_attempts: int = 3,
        retry_delays: tuple[float, ...] = (2.0, 5.0, 10.0),
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_delays = retry_delays
        self._limiter = AsyncRateLimiter(min_interval)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
            headers=_DEFAULT_HEADERS,
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def resolve(self, url: str) -> ResolvedPost:
        canonical_url, shortcode = normalize_post_url(url)

        async def operation() -> ResolvedPost:
            await self._limiter.wait()
            token = await self._fetch_token()
            response = await self._search(
                {
                    "linkValue": canonical_url,
                    "date": int(time.time() * 1000),
                    "token": token,
                    "requestType": "2",
                    "serverType": "link",
                }
            )
            return self._parse_link_response(response, canonical_url, shortcode)

        return await self._with_retry(operation)

    async def resolve_profile(
        self, value: str, *, include_stories: bool = True
    ) -> ResolvedCollection:
        """Resolve the latest posts (and optionally active stories) of a profile."""

        target = parse_target(value)
        if target.kind not in (TargetKind.PROFILE, TargetKind.STORIES):
            raise InvalidUrlError(f"Not a profile URL: {value!r}")
        if not target.username:
            raise InvalidUrlError(f"Profile URL has no username: {value!r}")

        server_type = "stories-posts"
        return await self._resolve_collection(
            target.username,
            server_type,
            kind="profile",
            include_stories=include_stories,
        )

    async def resolve_stories(self, value: str) -> ResolvedCollection:
        """Resolve the currently active stories of a profile."""

        target = parse_target(value)
        if target.kind not in (TargetKind.PROFILE, TargetKind.STORIES):
            raise InvalidUrlError(f"Not a profile or stories URL: {value!r}")
        if not target.username:
            raise InvalidUrlError(f"Stories URL has no username: {value!r}")

        return await self._resolve_collection(
            target.username, "stories", kind="stories"
        )

    async def _resolve_collection(
        self,
        username: str,
        server_type: str,
        *,
        kind: str,
        include_stories: bool = True,
    ) -> ResolvedCollection:
        async def operation() -> ResolvedCollection:
            await self._limiter.wait()
            token = await self._fetch_token()
            response = await self._search(
                {
                    "username": username,
                    "date": int(time.time() * 1000),
                    "token": token,
                    "requestType": "1",
                    "serverType": server_type,
                }
            )
            return self._parse_profile_response(
                response,
                username,
                server_type=server_type,
                kind=kind,
                include_stories=include_stories,
            )

        return await self._with_retry(operation)

    async def download(self, item: MediaItem, destination: Path) -> DownloadedFile:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f"{destination.name}.part")
        headers = {
            "User-Agent": _DEFAULT_HEADERS["User-Agent"],
            "Referer": f"{self.base_url}/",
        }

        try:
            async with self._http.stream(
                "GET", item.download_url, headers=headers
            ) as response:
                self._raise_for_download_status(response.status_code)
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
            raise DownloadTimeoutError(f"Таймаут скачивания {item.filename}") from exc
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

    async def _fetch_token(self) -> str:
        try:
            response = await self._http.get(f"{self.base_url}/connect/")
        except httpx.TimeoutException as exc:
            raise DownloadTimeoutError("Timed out fetching iqsaved token") from exc
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"Token request failed: {exc}") from exc

        if response.status_code in (429, 503):
            raise RateLimitedError(
                f"iqsaved returned {response.status_code} while issuing a token"
            )
        if response.status_code >= 400:
            raise EngineUnavailableError(
                f"iqsaved token endpoint returned {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise EngineUnavailableError(
                "iqsaved returned a non-JSON token response (likely rate limit or bot check)"
            ) from exc

        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise ProtocolError("iqsaved token response has no token")
        return token

    async def _search(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = socketio.AsyncClient(
            reconnection=False,
            logger=False,
            engineio_logger=False,
        )
        result: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )

        @client.on("searchResult")  # type: ignore[untyped-decorator]
        async def on_search_result(data: dict[str, Any]) -> None:
            if not result.done():
                result.set_result(data)

        try:
            await client.connect(
                self.base_url,
                transports=["websocket"],
                wait_timeout=self.timeout,
            )
            await client.emit("search", payload)
            return await asyncio.wait_for(result, timeout=self.timeout)
        except TimeoutError as exc:
            raise DownloadTimeoutError("iqsaved не ответил вовремя") from exc
        except socketio.exceptions.ConnectionError as exc:
            raise EngineUnavailableError(f"iqsaved socket connection failed: {exc}") from exc
        except socketio.exceptions.SocketIOError as exc:
            raise EngineUnavailableError(f"iqsaved socket error: {exc}") from exc
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(client.shutdown(), timeout=5.0)
            engineio_client = getattr(client, "eio", None)
            http_session = getattr(engineio_client, "http", None)
            if http_session is not None and not http_session.closed:
                with contextlib.suppress(Exception):
                    await http_session.close()

    def _parse_link_response(
        self, response: dict[str, Any], canonical_url: str, shortcode: str
    ) -> ResolvedPost:
        envelope = response.get("data")
        if not isinstance(envelope, dict):
            raise ProtocolError("iqsaved response has no data envelope")

        status = envelope.get("status")
        if status != "success":
            code = envelope.get("code")
            if code in _NOT_FOUND_CODES:
                raise ContentNotFoundError(
                    f"Пост {shortcode} недоступен, закрыт или удалён"
                )
            if code in _RETRYABLE_CODES:
                raise RateLimitedError(
                    f"iqsaved returned retryable code {code} for {shortcode}"
                )
            raise ProtocolError(
                f"iqsaved returned status={status!r} code={code!r} for {shortcode}"
            )

        post = envelope.get("data")
        if not isinstance(post, dict):
            raise ProtocolError("iqsaved success response has no post data")

        items: list[MediaItem] = []
        for raw_item in post.get("items") or []:
            if not isinstance(raw_item, dict):
                continue
            kind = (
                MediaKind.VIDEO
                if raw_item.get("type") == "video"
                else MediaKind.PHOTO
            )
            for download in raw_item.get("downloadLink") or []:
                if not isinstance(download, dict):
                    continue
                value = download.get("value")
                filename = download.get("filename")
                if not isinstance(value, str) or not value:
                    continue
                if not isinstance(filename, str) or not filename:
                    filename = f"{shortcode}_{len(items) + 1}"
                items.append(
                    MediaItem(
                        kind=kind,
                        filename=filename,
                        download_url=self._download_url(value, filename, viewer=False),
                        source_url=canonical_url,
                        index=len(items),
                    )
                )

        if not items:
            raise ProtocolError(f"iqsaved не вернул файлы для {shortcode}")

        taken_at = None
        if isinstance(post.get("takenAt"), (int, float)):
            taken_at = datetime.fromtimestamp(post["takenAt"], tz=UTC)

        return ResolvedPost(
            shortcode=shortcode,
            url=canonical_url,
            author=_as_optional_str(post.get("username")),
            caption=_as_optional_str(post.get("text")),
            taken_at=taken_at,
            likes=_as_optional_int(post.get("countLikes")),
            comments=_as_optional_int(post.get("countComments")),
            items=items,
            engine=self.name,
        )

    def _parse_profile_response(
        self,
        response: dict[str, Any],
        username: str,
        *,
        server_type: str,
        kind: str,
        include_stories: bool = True,
    ) -> ResolvedCollection:
        envelope = response.get("data")
        if not isinstance(envelope, dict):
            raise ProtocolError("iqsaved response has no data envelope")

        status = envelope.get("status")
        if status != "success":
            code = envelope.get("code")
            if code in _NOT_FOUND_CODES:
                raise ContentNotFoundError(
                    f"Профиль @{username} недоступен, закрыт или удалён"
                )
            if code in _RETRYABLE_CODES:
                raise RateLimitedError(
                    f"iqsaved returned retryable code {code} for @{username}"
                )
            raise ProtocolError(
                f"iqsaved returned status={status!r} code={code!r} for @{username}"
            )

        user = envelope.get("user")
        if not isinstance(user, dict):
            raise ProtocolError("iqsaved success response has no user data")

        raw_items: list[dict[str, Any]] = []
        if include_stories and server_type in ("stories", "stories-posts"):
            raw_items.extend(
                item for item in user.get("reels") or [] if isinstance(item, dict)
            )
        if server_type in ("posts", "stories-posts"):
            raw_items.extend(
                item for item in user.get("edges") or [] if isinstance(item, dict)
            )

        items: list[MediaItem] = []
        for raw_item in raw_items:
            is_video = bool(raw_item.get("is_video"))
            value = raw_item.get("video_url") if is_video else raw_item.get("display_url")
            filename = (
                raw_item.get("video_url_filename")
                if is_video
                else raw_item.get("display_url_filename")
            )
            if not isinstance(value, str) or not value:
                continue
            if not isinstance(filename, str) or not filename:
                suffix = "mp4" if is_video else "jpg"
                filename = f"{username}_{len(items) + 1}.{suffix}"

            items.append(
                MediaItem(
                    kind=MediaKind.VIDEO if is_video else MediaKind.PHOTO,
                    filename=filename,
                    download_url=self._download_url(value, filename, viewer=True),
                    source_url=f"https://www.instagram.com/{username}/",
                    index=len(items),
                    content_type="video/mp4" if is_video else "image/jpeg",
                )
            )

        if not items:
            if user.get("is_private"):
                raise ContentNotFoundError(f"Профиль @{username} закрыт")
            if server_type == "stories":
                raise ContentNotFoundError(f"У @{username} нет активных stories")
            raise ContentNotFoundError(
                f"У @{username} нет доступных публикаций или stories"
            )

        return ResolvedCollection(
            title=_as_optional_str(user.get("full_name")) or username,
            url=f"https://www.instagram.com/{username}/",
            author=username,
            caption=_as_optional_str(user.get("biography")),
            items=items,
            engine=self.name,
            kind=kind,
        )

    def _download_url(self, value: str, filename: str, *, viewer: bool) -> str:
        endpoint = "img2.php" if viewer else "img.php"
        return (
            f"{IQSAVED_CDN_URL}/{endpoint}"
            f"?url={quote(value, safe='')}"
            f"&filename={quote(filename, safe='')}"
        )

    async def _with_retry(
        self, operation: Callable[[], Awaitable[_T]]
    ) -> _T:
        last_error: EngineUnavailableError | None = None
        for attempt in range(self.max_attempts):
            try:
                return await operation()
            except (RateLimitedError, DownloadTimeoutError, EngineUnavailableError) as exc:
                last_error = exc
                if attempt == self.max_attempts - 1:
                    break
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                await asyncio.sleep(delay)
        if last_error is None:
            raise EngineUnavailableError("Запрос к iqsaved не удался")
        raise last_error

    @staticmethod
    def _raise_for_download_status(status_code: int) -> None:
        if status_code in _NOT_FOUND_CODES:
            raise ContentNotFoundError(f"Медиа недоступно (HTTP {status_code})")
        if status_code in _RETRYABLE_CODES or status_code >= 500:
            raise RateLimitedError(f"CDN вернул HTTP {status_code}")
        if status_code >= 400:
            raise EngineUnavailableError(f"CDN вернул HTTP {status_code}")


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
