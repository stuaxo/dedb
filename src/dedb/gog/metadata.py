"""GOG build-dependency metadata, cached globally by game id.

Shared across `listgog` and `downloadgog`, so a game we've already
classified - including one we've decided isn't worth downloading - never
needs its metadata re-fetched from GOG on a later run, unless refresh=True
is passed. Lives alongside dedbconf.toml under the XDG config directory,
not in the downloads folder, since it covers every owned game we've ever
looked at, not just downloaded ones.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..settings import CONFIG_DIR
from .client import classify_dependencies, fetch_dependencies
from .models import GogMetadata

CACHE_PATH = CONFIG_DIR / "gog" / "metadata_cache.json"


class MetadataCache:
    """An on-disk JSON cache of GOG dependency metadata, loaded lazily -
    once, on first use - rather than re-read and re-parsed from disk on
    every lookup, as a plain get_metadata() function backed by a file
    would otherwise do. Written back only when a new entry is added."""

    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        self._entries: dict[str, GogMetadata] | None = None

    def _entries_loaded(self) -> dict[str, GogMetadata]:
        if self._entries is None:
            if self.path.is_file():
                raw = json.loads(self.path.read_text())
                self._entries = {name: GogMetadata.model_validate(entry) for name, entry in raw.items()}
            else:
                self._entries = {}
        return self._entries

    def get(self, gamename: str, product_id: str, *, refresh: bool = False) -> GogMetadata:
        """Return cached dependency metadata for a game, fetching it from
        GOG and caching it if this is the first time we've seen it, or if
        refresh is requested."""
        entries = self._entries_loaded()
        if not refresh and gamename in entries:
            return entries[gamename]

        dependencies = fetch_dependencies(product_id)
        entries[gamename] = GogMetadata(
            gamename=gamename,
            product_id=product_id,
            dependencies=dependencies,
            classification=classify_dependencies(dependencies),
            fetched_at=datetime.now(timezone.utc),
        )
        self._save(entries)
        return entries[gamename]

    def _save(self, entries: dict[str, GogMetadata]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {name: metadata.model_dump(mode="json") for name, metadata in entries.items()}
        self.path.write_text(json.dumps(raw, indent=2))


_default_cache = MetadataCache()


def get_metadata(gamename: str, product_id: str, *, refresh: bool = False) -> GogMetadata:
    return _default_cache.get(gamename, product_id, refresh=refresh)
