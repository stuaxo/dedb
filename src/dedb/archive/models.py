"""Pydantic models for archive.org DOS item metadata."""

from datetime import datetime

from pydantic import BaseModel

from ..core import short_target


class ArchiveItemInfo(BaseModel):
    """One item's DOS-emulation fields plus the file to download (see
    `fetch_item`). Uncached - see `ArchiveMetadata`."""

    identifier: str
    title: str | None = None
    year: str | None = None
    emulator: str
    emulator_ext: str
    emulator_start: str
    download_filename: str
    download_url: str


class ArchiveMetadata(ArchiveItemInfo):
    """`ArchiveItemInfo` plus `fetched_at` - the cached/persisted form."""

    fetched_at: datetime


class ArchiveFavorite(BaseModel):
    """One entry in an archive.org user's public favorites."""

    identifier: str
    title: str | None = None
    year: str | None = None

    @property
    def target(self) -> str:
        """`archive:<identifier>`."""
        return short_target("archive", self.identifier)
