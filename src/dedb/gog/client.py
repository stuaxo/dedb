"""Thin wrappers around lgogdownloader and GOG's public, unauthenticated
Galaxy content-system API.

Each build's metadata is zlib-compressed JSON with a "dependencies" field,
e.g. ["DOSBox074_2CS"] or ["ScummVM"]. This is the only way to identify a
game's runtime without downloading it.
"""

import json
import subprocess
import urllib.error
import urllib.request
import zlib

from .models import OwnedGame

BUILDS_URL = "https://content-system.gog.com/products/{product_id}/os/windows/builds?generation=2"

# Errors fetch_dependencies() can raise: network failure, no gen-2 build,
# corrupt zlib payload, or malformed JSON. Shared so callers that need to
# handle a lookup failing don't each repeat this tuple.
FETCH_ERRORS = (urllib.error.URLError, LookupError, zlib.error, json.JSONDecodeError)


def owned_games() -> list[OwnedGame]:
    """Return all owned Windows-platform games. Downloads nothing."""
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
    return [OwnedGame(gamename=name, product_id=pid) for name, pid in seen.items()]


def fetch_dependencies(product_id: str) -> list[str] | None:
    """Fetch a product's "dependencies" field from GOG's public Galaxy
    build manifest."""
    with urllib.request.urlopen(BUILDS_URL.format(product_id=product_id), timeout=10) as resp:
        builds = json.loads(resp.read())

    build = next((b for b in builds.get("items", []) if b.get("generation") == 2), None)
    if build is None:
        raise LookupError("no generation-2 build available")

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
