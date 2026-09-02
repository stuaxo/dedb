"""archive.org item metadata, cached by identifier under the XDG config dir.

Mirrors `dedb.gog.metadata`: covers every item ever looked up (not just
downloaded ones), so a lookup never repeats unless ``refresh=True``.
"""

from datetime import datetime, timezone

from ..metadata_cache import JsonMetadataCache
from ..settings import CONFIG_DIR
from .client import fetch_item
from .models import ArchiveMetadata

CACHE_PATH = CONFIG_DIR / "archive" / "metadata_cache.json"


def _fetch(identifier: str) -> ArchiveMetadata:
    info = fetch_item(identifier)
    return ArchiveMetadata(**info.model_dump(), fetched_at=datetime.now(timezone.utc))


_cache = JsonMetadataCache(CACHE_PATH, ArchiveMetadata, _fetch)


def get_metadata(
    identifier: str, *, refresh: bool = False, offline: bool = False
) -> ArchiveMetadata:
    return _cache.get(identifier, refresh=refresh, offline=offline)
