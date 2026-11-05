from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .db_models import JobKind, JobStatus


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JobFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    size: int
    content_type: str | None = None
    kind: str
    position: int


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    normalized_url: str | None = None
    kind: JobKind
    status: JobStatus
    progress: int
    total_items: int
    downloaded_items: int
    author: str | None = None
    caption: str | None = None
    title: str | None = None
    error: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[JobFileOut] = Field(default_factory=list)


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class JobCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    include_stories: bool = True
    include_highlights: bool = False


class BatchJobCreate(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=50)
    include_stories: bool = True
    include_highlights: bool = False


class BatchError(BaseModel):
    url: str
    error: str


class BatchJobOut(BaseModel):
    jobs: list[JobOut]
    errors: list[BatchError]


class StatsOut(BaseModel):
    total: int
    queued: int
    running: int
    success: int
    partial: int
    failed: int


class AppConfigOut(BaseModel):
    highlights_available: bool
    highlights_reason: str | None = None
    max_batch_size: int
    job_ttl_hours: int
