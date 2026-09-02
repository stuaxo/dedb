"""Generic on-disk cache for pydantic metadata models, keyed by a string.

`dedb.gog.metadata` and `dedb.archive.metadata` are thin wrappers over this -
each injects the fetch that produces its model on a cache miss.
"""

import json
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


class OfflineError(RuntimeError):
    """Raised for an --offline request that has no cached data to answer it."""


class MetadataCache(Generic[M]):
    """A JSON file of ``{key: model.model_dump()}``, loaded lazily and rewritten
    when a new entry is added.

    On a miss (or ``refresh``), ``fetch(key, *args, **kwargs)`` produces the
    model; ``offline=True`` raises `OfflineError` instead of fetching.
    """

    def __init__(self, path: Path, model_cls: type[M], fetch: Callable[..., M]):
        self.path = path
        self._model_cls = model_cls
        self._fetch = fetch

    @cached_property
    def _cached_entries(self) -> dict[str, M]:
        if self.path.is_file():
            raw = json.loads(self.path.read_text())
            return {k: self._model_cls.model_validate(v) for k, v in raw.items()}
        return {}

    def get(
        self,
        key: str,
        *fetch_args,
        refresh: bool = False,
        offline: bool = False,
        **fetch_kwargs,
    ) -> M:
        if not refresh and key in self._cached_entries:
            return self._cached_entries[key]

        if offline:
            raise OfflineError(
                f"No cached metadata for '{key}' - run once without --offline first."
            )

        self._cached_entries[key] = self._fetch(key, *fetch_args, **fetch_kwargs)
        self._save()
        return self._cached_entries[key]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {k: v.model_dump(mode="json") for k, v in self._cached_entries.items()}
        self.path.write_text(json.dumps(raw, indent=2))
