"""Pydantic models for archive.org DOS item metadata."""

from datetime import datetime

from pydantic import BaseModel


class ArchiveItemInfo(BaseModel):
    """DOS-emulation fields resolved from one archive.org item's
    metadata (see dedb.archive.client.fetch_item), plus which of its
    files to download. Not yet cached - see ArchiveMetadata."""

    identifier: str
    title: str | None = None
    year: str | None = None
    emulator: str
    emulator_ext: str
    emulator_start: str
    download_filename: str
    download_url: str


class ArchiveMetadata(ArchiveItemInfo):
    """ArchiveItemInfo plus when it was fetched - the cached form,
    copied into each downloaded item's metadata.json."""

    fetched_at: datetime


class ArchiveFavorite(BaseModel):
    """One entry in an archive.org user's public favorites, as returned by
    the advancedsearch API - just enough to list and to build an
    `archive://<identifier>` target."""

    identifier: str
    title: str | None = None
    year: str | None = None


class GameMetadataFile(BaseModel):
    """Schema of downloads/<identifier>/metadata.json. Namespaced by
    source, mirroring dedb.gog.models.GameMetadataFile, so other kinds
    of per-game data can live alongside "archive" later."""

    archive: ArchiveMetadata
