from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from .errors import InvalidUrlError

_INSTAGRAM_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
    "l.instagram.com",
}

_POST_KINDS = {"p", "reel", "reels", "tv"}
_RESERVED_PROFILE_PATHS = {
    "p",
    "reel",
    "reels",
    "tv",
    "stories",
    "explore",
    "accounts",
    "direct",
    "about",
    "legal",
    "developer",
    "api",
}
_SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]{5,}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def normalize_post_url(value: str) -> tuple[str, str]:
    """Return (canonical_url, shortcode) for an Instagram post/reel URL.

    Query parameters such as ?srtk=, ?xtok= and ?psln= are intentionally dropped:
    they occasionally break the upstream parser.
    """

    raw = value.strip()
    if not raw:
        raise InvalidUrlError("Пустая ссылка")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower().split(":")[0]
    if host not in _INSTAGRAM_HOSTS:
        raise InvalidUrlError(f"Это не ссылка Instagram: {value!r}")

    segments = [segment for segment in parsed.path.split("/") if segment]
    for index, segment in enumerate(segments[:-1]):
        if segment not in _POST_KINDS:
            continue

        shortcode = segments[index + 1]
        if not _SHORTCODE_RE.fullmatch(shortcode):
            raise InvalidUrlError(f"Некорректный shortcode Instagram: {shortcode!r}")

        kind = "reel" if segment == "reels" else segment
        return f"https://www.instagram.com/{kind}/{shortcode}/", shortcode

    raise InvalidUrlError(f"Неподдерживаемая ссылка Instagram: {value!r}")


def normalize_username(value: str) -> str:
    """Accept a username or a profile URL and return the bare username."""

    raw = value.strip().lstrip("@")
    if not raw:
        raise InvalidUrlError("Пустое имя пользователя")

    if "://" in raw or raw.startswith("www.") or raw.startswith("instagram.com"):
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.netloc or "").lower().split(":")[0]
        if host not in _INSTAGRAM_HOSTS:
            raise InvalidUrlError(f"Это не ссылка Instagram: {value!r}")
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            raise InvalidUrlError(f"В ссылке на профиль нет имени пользователя: {value!r}")
        username = segments[0]
        if username.lower() in _RESERVED_PROFILE_PATHS:
            raise InvalidUrlError(f"Это не ссылка на профиль: {value!r}")
    else:
        username = raw

    if not _USERNAME_RE.fullmatch(username):
        raise InvalidUrlError(f"Некорректное имя пользователя Instagram: {username!r}")
    return username


class TargetKind(StrEnum):
    POST = "post"
    PROFILE = "profile"
    STORIES = "stories"
    HIGHLIGHTS = "highlights"


@dataclass(frozen=True, slots=True)
class Target:
    kind: TargetKind
    url: str
    username: str | None = None
    shortcode: str | None = None
    highlight_id: str | None = None


def parse_target(value: str) -> Target:
    """Classify an Instagram URL or username into a supported target."""

    raw = value.strip()
    if not raw:
        raise InvalidUrlError("Пустая ссылка")

    if "://" not in raw and "/" not in raw:
        username = normalize_username(raw)
        return Target(
            kind=TargetKind.PROFILE,
            url=f"https://www.instagram.com/{username}/",
            username=username,
        )

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower().split(":")[0]
    if host not in _INSTAGRAM_HOSTS:
        raise InvalidUrlError(f"Это не ссылка Instagram: {value!r}")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise InvalidUrlError(f"Неподдерживаемая ссылка Instagram: {value!r}")

    if segments[0] == "stories":
        if len(segments) >= 3 and segments[1].lower() == "highlights":
            highlight_id = segments[2]
            return Target(
                kind=TargetKind.HIGHLIGHTS,
                url=f"https://www.instagram.com/stories/highlights/{highlight_id}/",
                highlight_id=highlight_id,
            )
        if len(segments) >= 2:
            username = normalize_username(segments[1])
            return Target(
                kind=TargetKind.STORIES,
                url=f"https://www.instagram.com/stories/{username}/",
                username=username,
            )
        raise InvalidUrlError(f"В ссылке на stories нет имени пользователя: {value!r}")

    if any(segment in _POST_KINDS for segment in segments):
        canonical_url, shortcode = normalize_post_url(raw)
        return Target(
            kind=TargetKind.POST,
            url=canonical_url,
            shortcode=shortcode,
        )

    if segments[0].lower() in _RESERVED_PROFILE_PATHS or segments[0] == "s":
        raise InvalidUrlError(f"Неподдерживаемая ссылка Instagram: {value!r}")

    username = normalize_username(segments[0])
    return Target(
        kind=TargetKind.PROFILE,
        url=f"https://www.instagram.com/{username}/",
        username=username,
    )
