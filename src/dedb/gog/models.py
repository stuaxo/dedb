"""Pydantic models for GOG game metadata."""

from datetime import datetime

from pydantic import BaseModel

from ..core import short_target


class GOGGame(BaseModel):
    gamename: str
    product_id: str

    @property
    def target(self) -> str:
        """`gog:<gamename>`."""
        return short_target("gog", self.gamename)


class GogProfile(BaseModel):
    """One playTask from a game's goggame-*.info - a launch option GOG's
    own installer would have created a shortcut for (e.g. "Play",
    "Multiplayer Host"). Only file-launchable tasks are recorded; document
    /URL tasks (e.g. "Support") are skipped when parsing."""

    name: str
    category: str | None = None
    is_primary: bool = False
    path: str = ""
    arguments: str = ""
    working_dir: str = ""
    # Basenames of every file passed via -conf in `arguments`, e.g.
    # ["dosbox_warcraft.conf", "dosbox_warcraft_single.conf"].
    conf_files: list[str] = []


class GogMetadata(BaseModel):
    """What we know about a GOG product: its runtime dependencies (cached
    globally, so games we decide not to download aren't re-fetched on
    every run) and, once downloaded, its launch profiles. Copied into
    each downloaded game's metadata.json."""

    gamename: str
    product_id: str
    dependencies: list[str] | None
    classification: str
    fetched_at: datetime
    profiles: list[GogProfile] = []


class GameMetadataFile(BaseModel):
    """Schema of downloads/<game_id>/metadata.json. Namespaced by source
    so other kinds of per-game data can live alongside "gog" later."""

    gog: GogMetadata
