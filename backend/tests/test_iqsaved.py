from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.downloader.engines.iqsaved import IqSavedEngine
from app.downloader.errors import (
    ContentNotFoundError,
    ProtocolError,
    RateLimitedError,
)
from app.downloader.models import MediaItem, MediaKind


def success_payload() -> dict[str, Any]:
    return {
        "data": {
            "status": "success",
            "code": 200,
            "data": {
                "username": "tester",
                "text": "hello world",
                "takenAt": 1_700_000_000,
                "countLikes": 10,
                "countComments": 2,
                "items": [
                    {
                        "type": "photo",
                        "downloadLink": [
                            {
                                "filename": "a b.jpg",
                                "value": "https://scontent.example/a?x=1&y=2",
                            }
                        ],
                    },
                    {
                        "type": "video",
                        "downloadLink": [
                            {"filename": "v.mp4", "value": "https://scontent.example/v"}
                        ],
                    },
                ],
            },
        }
    }


@pytest.fixture
async def engine() -> AsyncGenerator[IqSavedEngine, None]:
    client = httpx.AsyncClient()
    instance = IqSavedEngine(min_interval=0, http_client=client)
    try:
        yield instance
    finally:
        await client.aclose()


async def test_parse_link_response(engine: IqSavedEngine) -> None:
    post = engine._parse_link_response(
        success_payload(),
        "https://www.instagram.com/p/DWHCJrgjVHd/",
        "DWHCJrgjVHd",
    )

    assert post.shortcode == "DWHCJrgjVHd"
    assert post.author == "tester"
    assert post.caption == "hello world"
    assert post.likes == 10
    assert post.comments == 2
    assert post.engine == "iqsaved"
    assert [item.kind for item in post.items] == [MediaKind.PHOTO, MediaKind.VIDEO]
    assert [item.filename for item in post.items] == ["a b.jpg", "v.mp4"]
    assert post.items[0].download_url == (
        "https://cdn.iqsaved.com/img.php"
        "?url=https%3A%2F%2Fscontent.example%2Fa%3Fx%3D1%26y%3D2"
        "&filename=a%20b.jpg"
    )
    assert post.items[1].index == 1


@pytest.mark.parametrize(
    ("code", "error"),
    [(403, ContentNotFoundError), (404, ContentNotFoundError), (430, RateLimitedError)],
)
async def test_parse_error_codes(
    engine: IqSavedEngine, code: int, error: type[Exception]
) -> None:
    payload = {"data": {"status": "error", "code": code}}
    with pytest.raises(error):
        engine._parse_link_response(payload, "https://www.instagram.com/p/ABCdef123/", "ABCdef123")


async def test_parse_rejects_empty_items(engine: IqSavedEngine) -> None:
    payload = {"data": {"status": "success", "data": {"items": []}}}
    with pytest.raises(ProtocolError):
        engine._parse_link_response(payload, "https://www.instagram.com/p/ABCdef123/", "ABCdef123")


async def test_parse_rejects_missing_envelope(engine: IqSavedEngine) -> None:
    with pytest.raises(ProtocolError):
        engine._parse_link_response({}, "https://www.instagram.com/p/ABCdef123/", "ABCdef123")


async def test_download_writes_file(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "cdn.iqsaved.com"
        return httpx.Response(
            200,
            content=b"\xff\xd8fake-jpeg",
            headers={"content-type": "image/jpeg"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    instance = IqSavedEngine(min_interval=0, http_client=client)
    destination = tmp_path / "photo.jpg"
    try:
        downloaded = await instance.download(
            MediaItem(
                kind=MediaKind.PHOTO,
                filename="photo.jpg",
                download_url="https://cdn.iqsaved.com/img.php?url=x&filename=photo.jpg",
            ),
            destination,
        )
    finally:
        await client.aclose()

    assert destination.read_bytes() == b"\xff\xd8fake-jpeg"
    assert not destination.with_name("photo.jpg.part").exists()
    assert downloaded.size == len(b"\xff\xd8fake-jpeg")
    assert downloaded.content_type == "image/jpeg"


async def test_download_maps_not_found(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    instance = IqSavedEngine(min_interval=0, http_client=client)
    try:
        with pytest.raises(ContentNotFoundError):
            await instance.download(
                MediaItem(
                    kind=MediaKind.PHOTO,
                    filename="photo.jpg",
                    download_url="https://cdn.iqsaved.com/img.php?url=x&filename=photo.jpg",
                ),
                tmp_path / "photo.jpg",
            )
    finally:
        await client.aclose()

    assert not (tmp_path / "photo.jpg.part").exists()


async def test_resolve_retries_rate_limit(
    engine: IqSavedEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = {"token": 0, "search": 0}

    async def fake_token() -> str:
        attempts["token"] += 1
        if attempts["token"] < 3:
            raise RateLimitedError("503")
        return "token"

    async def fake_search(payload: dict[str, Any]) -> dict[str, Any]:
        attempts["search"] += 1
        return success_payload()

    engine.retry_delays = (0.0, 0.0, 0.0)
    monkeypatch.setattr(engine, "_fetch_token", fake_token)
    monkeypatch.setattr(engine, "_search", fake_search)

    post = await engine.resolve("https://www.instagram.com/p/DWHCJrgjVHd/?srtk=abc")

    assert post.shortcode == "DWHCJrgjVHd"
    assert attempts == {"token": 3, "search": 1}


def profile_payload() -> dict[str, Any]:
    return {
        "data": {
            "status": "success",
            "code": 200,
            "serverType": "stories-posts",
            "user": {
                "username": "tester",
                "full_name": "Test User",
                "biography": "bio",
                "is_private": False,
                "edges": [
                    {
                        "is_video": False,
                        "display_url": "https://scontent.example/post",
                        "display_url_filename": "post.jpg",
                        "video_url": "",
                        "video_url_filename": "",
                    },
                    {
                        "is_video": True,
                        "display_url": "https://scontent.example/cover",
                        "display_url_filename": "cover.jpg",
                        "video_url": "https://scontent.example/video",
                        "video_url_filename": "video.mp4",
                    },
                ],
                "reels": [
                    {
                        "is_video": True,
                        "display_url": "https://scontent.example/story-cover",
                        "display_url_filename": "story.jpg",
                        "video_url": "https://scontent.example/story-video",
                        "video_url_filename": "story.mp4",
                    }
                ],
            },
        }
    }


async def test_parse_profile_response(engine: IqSavedEngine) -> None:
    collection = engine._parse_profile_response(
        profile_payload(),
        "tester",
        server_type="stories-posts",
        kind="profile",
    )

    assert collection.title == "Test User"
    assert collection.author == "tester"
    assert collection.caption == "bio"
    assert [item.kind for item in collection.items] == [
        MediaKind.VIDEO,
        MediaKind.PHOTO,
        MediaKind.VIDEO,
    ]
    assert [item.filename for item in collection.items] == [
        "story.mp4",
        "post.jpg",
        "video.mp4",
    ]
    assert collection.items[0].download_url.startswith(
        "https://cdn.iqsaved.com/img2.php?"
    )


async def test_parse_private_profile(engine: IqSavedEngine) -> None:
    payload = {
        "data": {
            "status": "success",
            "user": {"username": "tester", "is_private": True, "edges": [], "reels": []},
        }
    }
    with pytest.raises(ContentNotFoundError):
        engine._parse_profile_response(
            payload, "tester", server_type="stories-posts", kind="profile"
        )
