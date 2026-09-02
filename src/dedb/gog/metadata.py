"""GOG build-dependency metadata, cached by game id under the XDG config dir.

Covers every owned game ever looked up (including ones not worth
downloading), so a lookup never repeats unless ``refresh=True``.
"""

from datetime import datetime, timezone

from ..core.metadata_cache import MetadataCache
from ..core.settings import scheme_config_path
from .client import classify_dependencies, fetch_dependencies
from .models import GogMetadata

CACHE_PATH = scheme_config_path("gog", "metadata_cache.json")


def _fetch(gamename: str, product_id: str, *, verbose: bool = False) -> GogMetadata:
    dependencies = fetch_dependencies(product_id, verbose=verbose)
    return GogMetadata(
        gamename=gamename,
        product_id=product_id,
        dependencies=dependencies,
        classification=classify_dependencies(dependencies),
        fetched_at=datetime.now(timezone.utc),
    )


_cache = MetadataCache(CACHE_PATH, GogMetadata, _fetch)


def get_metadata(
    gamename: str,
    product_id: str,
    *,
    refresh: bool = False,
    offline: bool = False,
    verbose: bool = False,
) -> GogMetadata:
    return _cache.get(gamename, product_id, refresh=refresh, offline=offline, verbose=verbose)
