"""The schema of ``<download_dir>/<scheme>/<id>/metadata.json`` - one
versioned envelope shared by every backend.

The common fields (identity, title, classification, launch profiles) are
:class:`dedb.core.local.GameDescription`, shared with the in-memory
:class:`~dedb.core.local.LocalGame` - they sit at the top level so ``core``
can read them without touching a backend model. The backend's own metadata
model is dumped verbatim into ``source`` and stays opaque here.

``read()`` upgrades a pre-envelope (v1) file - ``{"gog": {...}}`` /
``{"archive": {...}}`` - on the way through, so old downloads keep working
with no re-download. The file is rewritten in the new shape on the next
``dedb download --refreshmetadata`` or convert.
"""

import json
from pathlib import Path

from pydantic import Field

from .local import GameDescription, LocalGame

CURRENT_SCHEMA = 2


class GameMetadataFile(GameDescription):
    """The persisted form of :class:`GameDescription` - the shared fields
    plus a schema version and the backend's own opaque metadata blob."""

    schema_version: int = CURRENT_SCHEMA
    # The backend's own metadata model, dumped with model_dump(mode="json").
    # Opaque to core; each backend validates it back into its own model.
    source: dict = Field(default_factory=dict)

    def as_local_game(self, *, converted: bool, launch_profiles: "list | None" = None) -> LocalGame:
        """The :class:`LocalGame` view of this envelope: the shared fields
        as-is, ``converted`` from the layout (whether a ``dosemu.conf`` has
        been generated), and (for a migrated file whose profiles the
        backend re-derived) an optional ``launch_profiles`` override."""
        data = {name: getattr(self, name) for name in GameDescription.model_fields}
        if launch_profiles is not None:
            data["launch_profiles"] = launch_profiles
        return LocalGame(**data, converted=converted)

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
