from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"


class MediaItem(BaseModel):
    kind: MediaKind
    filename: str
    download_url: str
    source_url: str | None = None
    index: int = 0
    content_type: str | None = None
    engine: str = "iqsaved"


class ResolvedPost(BaseModel):
    shortcode: str
    url: str
    author: str | None = None
    caption: str | None = None
    taken_at: datetime | None = None
    likes: int | None = None
    comments: int | None = None
    items: list[MediaItem] = Field(default_factory=list)
    engine: str = "iqsaved"


class ResolvedCollection(BaseModel):
    """A profile, stories feed or highlights collection."""

    title: str
    url: str
    author: str | None = None
    caption: str | None = None
    items: list[MediaItem] = Field(default_factory=list)
    engine: str = "iqsaved"
    kind: str = "profile"


class DownloadedFile(BaseModel):
    path: str
    filename: str
    size: int
    content_type: str | None = None
