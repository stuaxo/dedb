"""Thin wrappers around lgogdownloader and GOG's public, unauthenticated
Galaxy content-system API.

Each build's metadata is zlib-compressed JSON with a "dependencies" field,
e.g. ["DOSBox074_2CS"] or ["ScummVM"]. This is the only way to identify a
game's runtime without downloading it.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path

from ..core.client import BaseClient
from ..core.metadata_cache import (
    OfflineError,
)  # re-exported: GOGClient and lsgog/classify use it
from ..core.settings import scheme_config_path
from .models import GOGGame

__all__ = [
    "FETCH_ERRORS",
    "GOGClient",
    "OfflineError",
    "classify_dependencies",
    "fetch_dependencies",
]

BUILDS_URL = "https://content-system.gog.com/products/{product_id}/os/windows/builds?generation=2"

# Errors fetch_dependencies() can raise: network failure, no gen-2 build,
# corrupt zlib payload, or malformed JSON. Shared so callers that need to
# handle a lookup failing don't each repeat this tuple.
FETCH_ERRORS = (urllib.error.URLError, LookupError, zlib.error, json.JSONDecodeError)

# Cache of the last GOGClient.get_list() result, so --offline has something to read
# instead of calling lgogdownloader (which always contacts GOG, even with
# its own --use-cache, to check login status).
OWNED_GAMES_CACHE_PATH = scheme_config_path("gog", "owned_games_cache.json")


def _log_connecting(url: str, *, verbose: bool) -> None:
    if verbose:
        print(f"Connecting to GOG: {url}", file=sys.stderr)


class GOGClient(BaseClient):
    default_name = "owned"

    def has_default_list(self) -> bool:
        return True

    def download(self, name: str, dest_dir: Path) -> None:
        """Download one game via lgogdownloader. Raises subprocess.CalledProcessError on failure."""
        subprocess.run(
            [
                "lgogdownloader",
                "--download",
                "--game",
                f"^{name}$",
                "--platform",
                "w",
                "--include",
                "installers",
            ],
            cwd=dest_dir,
            check=True,
        )

    def get_list(
        self, name: str | None = None, *, verbose: bool = False, offline: bool = False, **kwargs
    ) -> list[GOGGame]:
        """Return all owned Windows-platform games. Downloads nothing, but by
        default still contacts GOG (via lgogdownloader) on every call - this is
        the pause `lsgog`/`downloadgog` show at startup. Pass offline=True to
        reuse the last successful result instead, with no network access."""
        if offline:
            if not OWNED_GAMES_CACHE_PATH.is_file():
                raise OfflineError(
                    f"No cached owned-games list at {OWNED_GAMES_CACHE_PATH} yet - run once without --offline first."
                )
            raw = json.loads(OWNED_GAMES_CACHE_PATH.read_text())
            return [GOGGame.model_validate(g) for g in raw]

        _log_connecting(
            "lgogdownloader --list=json --platform w (contacts gog.com to refresh login/library)",
            verbose=verbose,
        )
        result = subprocess.run(
            ["lgogdownloader", "--list=json", "--platform", "w"],
            capture_output=True,
            text=True,
            check=True,
        )
        games = json.loads(result.stdout)
        seen: dict[str, str] = {}
        for g in games:
            seen[g["gamename"]] = g["product_id"]
        owned = [GOGGame(gamename=name, product_id=pid) for name, pid in seen.items()]

        OWNED_GAMES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        OWNED_GAMES_CACHE_PATH.write_text(json.dumps([g.model_dump(mode="json") for g in owned]))

        return owned


def fetch_dependencies(product_id: str, *, verbose: bool = False) -> list[str] | None:
    """Fetch a product's "dependencies" field from GOG's public Galaxy
    build manifest."""
    builds_url = BUILDS_URL.format(product_id=product_id)
    _log_connecting(builds_url, verbose=verbose)
    with urllib.request.urlopen(builds_url, timeout=10) as resp:
        builds = json.loads(resp.read())

    build = next((b for b in builds.get("items", []) if b.get("generation") == 2), None)
    if build is None:
        raise LookupError("no generation-2 build available")

    _log_connecting(build["link"], verbose=verbose)
    with urllib.request.urlopen(build["link"], timeout=10) as resp:
        meta = json.loads(zlib.decompress(resp.read()))

    return meta.get("dependencies")


def classify_dependencies(deps: list[str] | None) -> str:
    if not deps:
        return "none"
    lowered = [d.lower() for d in deps]
    if any("dosbox" in d for d in lowered):
        return "dosbox"
    if any("scummvm" in d for d in lowered):
        return "scummvm"
    return "other (" + ", ".join(deps) + ")"
