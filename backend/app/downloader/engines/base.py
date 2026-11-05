from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import DownloadedFile, MediaItem, ResolvedPost


class DownloadEngine(Protocol):
    """Common interface for downloader engines (iqsaved, instaloader, ...)."""

    name: str

    async def resolve(self, url: str) -> ResolvedPost:
        """Resolve an Instagram URL into a post with downloadable media items."""

    async def download(self, item: MediaItem, destination: Path) -> DownloadedFile:
        """Download one media item to the given path."""

    async def close(self) -> None:
        """Release network resources."""
