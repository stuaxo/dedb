"""archive.org item metadata, cached globally by identifier.

Mirrors dedb.gog.metadata: an item we've already looked up - including
one we decided not to download - never needs re-fetching from
archive.org on a later run, unless refresh=True is passed. Lives
alongside dedbconf.toml under the XDG config directory, not in the
downloads folder, since it covers every item we've ever looked at, not
just downloaded ones.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..settings import CONFIG_DIR
from .client import fetch_item
from .models import ArchiveMetadata

CACHE_PATH = CONFIG_DIR / "archive" / "metadata_cache.json"


class OfflineError(RuntimeError):
    """Raised for an --offline request that has no cached data to answer it."""


class MetadataCache:
    """On-disk JSON cache of archive.org item metadata. Loaded once, on
    first use, and kept in memory after that. Written back only when a
    new entry is added."""

    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        self._entries: dict[str, ArchiveMetadata] | None = None

    def _entries_loaded(self) -> dict[str, ArchiveMetadata]:
        if self._entries is None:
            if self.path.is_file():
                raw = json.loads(self.path.read_text())
                self._entries = {identifier: ArchiveMetadata.model_validate(entry) for identifier, entry in raw.items()}
            else:
                self._entries = {}
        return self._entries

    def get(self, identifier: str, *, refresh: bool = False, offline: bool = False) -> ArchiveMetadata:
        """Return cached metadata for an item, fetching it from
        archive.org and caching it if this is the first time we've seen
        it, or if refresh is requested. offline=True raises
        OfflineError instead of fetching when there's no cached entry
        to fall back on."""
        entries = self._entries_loaded()
        if not refresh and identifier in entries:
            return entries[identifier]
        if offline:
            raise OfflineError(f"No cached metadata for '{identifier}' - run once without --offline first.")

        info = fetch_item(identifier)
        entries[identifier] = ArchiveMetadata(**info.model_dump(), fetched_at=datetime.now(timezone.utc))
        self._save(entries)
        return entries[identifier]

    def _save(self, entries: dict[str, ArchiveMetadata]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {identifier: metadata.model_dump(mode="json") for identifier, metadata in entries.items()}
        self.path.write_text(json.dumps(raw, indent=2))


_default_cache = MetadataCache()


def get_metadata(identifier: str, *, refresh: bool = False, offline: bool = False) -> ArchiveMetadata:
    return _default_cache.get(identifier, refresh=refresh, offline=offline)
