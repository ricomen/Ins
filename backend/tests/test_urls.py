from __future__ import annotations

import pytest

from app.downloader.errors import InvalidUrlError
from app.downloader.urls import normalize_post_url, normalize_username, parse_target


@pytest.mark.parametrize(
    ("raw", "expected_url", "expected_shortcode"),
    [
        (
            "https://www.instagram.com/p/DWHCJrgjVHd/?srtk=ZzFzbmxqNzVpbWc1",
            "https://www.instagram.com/p/DWHCJrgjVHd/",
            "DWHCJrgjVHd",
        ),
        (
            "https://instagram.com/reel/DeV8DLkOvfq/?psln=amZpcHB6MjVhN3Ix",
            "https://www.instagram.com/reel/DeV8DLkOvfq/",
            "DeV8DLkOvfq",
        ),
        (
            "https://m.instagram.com/reels/De5Yu15j6s1/",
            "https://www.instagram.com/reel/De5Yu15j6s1/",
            "De5Yu15j6s1",
        ),
        (
            "www.instagram.com/tv/ABCdef123/",
            "https://www.instagram.com/tv/ABCdef123/",
            "ABCdef123",
        ),
        (
            "https://www.instagram.com/p/ABCdef123/?utm_source=ig_web_copy_link#fragment",
            "https://www.instagram.com/p/ABCdef123/",
            "ABCdef123",
        ),
    ],
)
def test_normalize_post_url(raw: str, expected_url: str, expected_shortcode: str) -> None:
    assert normalize_post_url(raw) == (expected_url, expected_shortcode)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://example.com/p/ABCdef123/",
        "https://www.instagram.com/",
        "https://www.instagram.com/username/",
        "https://www.instagram.com/stories/username/123/",
        "https://www.instagram.com/p/abc/",
    ],
)
def test_normalize_post_url_rejects_unsupported(raw: str) -> None:
    with pytest.raises(InvalidUrlError):
        normalize_post_url(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("instagram", "instagram"),
        ("@instagram", "instagram"),
        ("https://www.instagram.com/instagram/", "instagram"),
        ("www.instagram.com/instagram/", "instagram"),
    ],
)
def test_normalize_username(raw: str, expected: str) -> None:
    assert normalize_username(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "@", "https://example.com/user/", "https://www.instagram.com/p/ABCdef123/", "bad name"],
)
def test_normalize_username_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidUrlError):
        normalize_username(raw)


@pytest.mark.parametrize(
    ("raw", "kind", "username", "shortcode"),
    [
        ("natgeo", "profile", "natgeo", None),
        ("https://www.instagram.com/natgeo/", "profile", "natgeo", None),
        ("https://www.instagram.com/p/ABCdef123/", "post", None, "ABCdef123"),
        ("https://www.instagram.com/reel/DeV8DLkOvfq/", "post", None, "DeV8DLkOvfq"),
        ("https://www.instagram.com/stories/natgeo/123/", "stories", "natgeo", None),
    ],
)
def test_parse_target(raw: str, kind: str, username: str | None, shortcode: str | None) -> None:
    target = parse_target(raw)
    assert target.kind.value == kind
    assert target.username == username
    assert target.shortcode == shortcode


def test_parse_highlight_target() -> None:
    target = parse_target("https://www.instagram.com/stories/highlights/17890000000000000/")
    assert target.kind.value == "highlights"
    assert target.highlight_id == "17890000000000000"
