"""Tests for dedb.core.metadata_cache.MetadataCache - the generic that
dedb.gog.metadata and dedb.archive.metadata are thin wrappers over.
"""

import pytest
from pydantic import BaseModel

from dedb.core.metadata_cache import MetadataCache, OfflineError


class Meta(BaseModel):
    key: str
    n: int


@pytest.fixture
def cache(tmp_path):
    calls = []

    def fetch(key, bump=0, *, verbose=False):
        calls.append((key, bump, verbose))
        return Meta(key=key, n=len(calls) + bump)

    c = MetadataCache(tmp_path / "cache.json", Meta, fetch)
    c.calls = calls  # type: ignore[attr-defined]
    return c


def test_miss_fetches_and_caches(cache):
    assert cache.get("a") == Meta(key="a", n=1)
    assert cache.get("a") == Meta(key="a", n=1)  # served from memory
    assert cache.calls == [("a", 0, False)]  # fetched once


def test_refresh_re_fetches_even_on_a_hit(cache):
    cache.get("a")
    assert cache.get("a", refresh=True) == Meta(key="a", n=2)
    assert len(cache.calls) == 2


def test_fetch_args_and_kwargs_are_forwarded(cache):
    cache.get("a", 10, verbose=True)
    assert cache.calls == [("a", 10, True)]


def test_offline_miss_raises_without_fetching(cache):
    with pytest.raises(OfflineError):
        cache.get("a", offline=True)
    assert cache.calls == []


def test_offline_hit_returns_the_cached_entry(cache):
    cache.get("a")
    assert cache.get("a", offline=True) == Meta(key="a", n=1)


def test_entries_survive_a_new_cache_over_the_same_file(cache, tmp_path):
    cache.get("a")
    cache.get("b", 5)

    reopened = MetadataCache(tmp_path / "cache.json", Meta, lambda *a, **k: pytest.fail("no fetch"))
    assert reopened.get("a") == Meta(key="a", n=1)
    assert reopened.get("b") == Meta(key="b", n=7)
