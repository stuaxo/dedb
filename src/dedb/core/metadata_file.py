"""The schema of ``<download_dir>/<scheme>/<id>/metadata.json`` - one
versioned envelope shared by every backend.

Common fields (identity, title, classification, launch profiles) sit at the
top level so ``core`` can read them without touching a backend model; the
backend's own metadata model is dumped verbatim into ``source`` and stays
opaque here.

``read()`` upgrades a pre-envelope (v1) file - ``{"gog": {...}}`` /
``{"archive": {...}}`` - on the way through, so old downloads keep working
with no re-download. The file is rewritten in the new shape on the next
``dedb download --refreshmetadata`` or convert.
"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .local import LaunchProfile

CURRENT_SCHEMA = 2


class GameMetadataFile(BaseModel):
    schema_version: int = CURRENT_SCHEMA
    scheme: str
    identifier: str
    title: str | None = None
    year: str | None = None
    classification: str | None = None
    downloaded_at: datetime | None = None
    launch_profiles: list[LaunchProfile] = []
    # The backend's own metadata model, dumped with model_dump(mode="json").
    # Opaque to core; each backend validates it back into its own model.
    source: dict = {}

    @classmethod
    def read(cls, path: Path) -> "GameMetadataFile":
        """Load ``path``, upgrading a v1 file on the way through. Raises
        ``OSError`` if it can't be read and ``ValueError`` (JSON or
        validation) if its contents don't make sense."""
        data = json.loads(path.read_text())
        if data.get("schema_version"):
            return cls.model_validate(data)
        return cls._from_v1(data)

    @classmethod
    def read_or_none(cls, path: Path) -> "GameMetadataFile | None":
        """``read()`` that returns None for a missing, unreadable or
        malformed file, for callers (``dedb ls``) that would rather show a
        thin entry than fail."""
        try:
            return cls.read(path)
        except (OSError, ValueError):
            return None

    @classmethod
    def _from_v1(cls, data: dict) -> "GameMetadataFile":
        """A v1 file is ``{<scheme>: <backend metadata blob>}`` with no
        ``schema_version``. Lift the fields common to every backend out of
        the blob and keep the whole blob as ``source``; leave
        ``launch_profiles`` empty (the backend re-derives them from the
        extracted files)."""
        scheme, blob = next(iter(data.items()))
        return cls.model_validate(
            {
                "schema_version": CURRENT_SCHEMA,
                "scheme": scheme,
                "identifier": blob.get("identifier") or blob.get("gamename") or scheme,
                "title": blob.get("title"),
                "year": blob.get("year"),
                "classification": blob.get("classification"),
                "downloaded_at": blob.get("fetched_at"),
                "launch_profiles": [],
                "source": blob,
            }
        )
