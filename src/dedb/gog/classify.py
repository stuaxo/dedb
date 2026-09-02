"""Classify every owned GOG game as dosbox/scummvm/none/other, checking
already-extracted local files first and falling back to (cached) GOG build
metadata. Shared by `lsgog` and `downloadgog` - `downloadgog --all`
downloads whatever this classifies as "dosbox".
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .client import FETCH_ERRORS, OfflineError
from .downloader import local_dosbox_status
from .layout import GogLayout
from .metadata import get_metadata
from .models import GOGGame


@dataclass
class GameStatus:
    classification: str
    source: str  # "local", "remote", "offline", or "error"


def classify_owned_games(
    games: Sequence[GOGGame],
    download_dir: Path | None,
    *,
    refresh: bool = False,
    verbose: bool = False,
    offline: bool = False,
) -> dict[str, GameStatus]:
    """Local extraction (if present) is always authoritative and never
    refreshed - refresh only forces re-fetching cached remote metadata.
    offline=True never contacts GOG: games without a local extraction or a
    prior cached fetch come back "unknown" instead."""
    status: dict[str, GameStatus] = {}
    for game in games:
        local = (
            local_dosbox_status(GogLayout(download_dir, game.gamename)) if download_dir else None
        )
        if local is not None:
            status[game.gamename] = GameStatus(local, "local")
            continue
        try:
            metadata = get_metadata(
                game.gamename, game.product_id, refresh=refresh, offline=offline, verbose=verbose
            )
            status[game.gamename] = GameStatus(metadata.classification, "remote")
        except OfflineError:
            status[game.gamename] = GameStatus("unknown", "offline")
        except FETCH_ERRORS as exc:
            status[game.gamename] = GameStatus(f"error: {exc}", "error")
    return status
