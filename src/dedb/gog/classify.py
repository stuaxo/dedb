"""Classify every owned GOG game as dosbox/scummvm/none/other, checking
already-extracted local files first and falling back to (cached) GOG build
metadata. Shared by `listgog` and `downloadgog` - with no curated list
configured, `downloadgog` downloads whatever this classifies as "dosbox".
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .client import FETCH_ERRORS
from .downloader import local_dosbox_status
from .layout import GameLayout
from .metadata import get_metadata
from .models import OwnedGame


@dataclass
class GameStatus:
    classification: str
    source: str  # "local", "remote", or "error"


def classify_owned_games(
    games: Sequence[OwnedGame], download_dir: Path | None, *, refresh: bool = False
) -> dict[str, GameStatus]:
    """Local extraction (if present) is always authoritative and never
    refreshed - refresh only forces re-fetching cached remote metadata."""
    status: dict[str, GameStatus] = {}
    for game in games:
        local = local_dosbox_status(GameLayout(download_dir, game.gamename)) if download_dir else None
        if local is not None:
            status[game.gamename] = GameStatus(local, "local")
            continue
        try:
            metadata = get_metadata(game.gamename, game.product_id, refresh=refresh)
            status[game.gamename] = GameStatus(metadata.classification, "remote")
        except FETCH_ERRORS as exc:
            status[game.gamename] = GameStatus(f"error: {exc}", "error")
    return status
