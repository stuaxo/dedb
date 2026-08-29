"""Thin wrapper around archive.org's public, unauthenticated metadata
API. Every archive.org "software" item that's playable via DOSBox
carries a small set of DOS emulation fields in its metadata (see
https://archive.org/details/msdos_Electro_Man_1992 for an example):
"emulator" (e.g. "dosbox"), "emulator_ext" (the extension of the
downloadable game archive, usually "zip") and "emulator_start" (the
path, relative to that archive's root, of the file to run). This is the
only way to identify what to download and how to launch it - unlike
GOG, archive.org items aren't "owned", so there's nothing to list or
authenticate against.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .models import ArchiveItemInfo

METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

# Errors fetch_item() can raise: network failure, malformed JSON.
FETCH_ERRORS = (urllib.error.URLError, json.JSONDecodeError)

_ITEM_URL_RE = re.compile(r"^https?://(?:www\.)?archive\.org/(?:details|download|metadata)/([^/?#]+)")


class NotDosItemError(LookupError):
    """Raised when an item has no "emulator"/"emulator_start" metadata -
    it isn't (or isn't recognisably) a DOSBox-playable archive.org item."""


def parse_identifier(value: str) -> str:
    """Accept either a bare archive.org identifier or a full item URL
    (details/download/metadata), e.g.
    https://archive.org/details/msdos_Electro_Man_1992, and return just
    the identifier."""
    match = _ITEM_URL_RE.match(value)
    return match.group(1) if match else value


def _scalar(value: object) -> str | None:
    """archive.org's metadata API returns a plain string for a
    single-valued field, but a list for one with multiple recorded
    values - normalise to "the first value, if any"."""
    if isinstance(value, list):
        return value[0] if value else None
    return value  # type: ignore[return-value]


def _pick_archive(candidates: list[str], meta: dict) -> str:
    """Choose which of several emulator_ext-matching files to download.

    An item that ships more than one archive (e.g. a shareware build
    alongside the registered version its player actually boots) names the
    one to mount as C: in its "dosbox_drive_c" metadata field - the same
    field archive.org's own in-browser DOSBox loader reads. Match it
    case-insensitively against the real file names; fall back to the first
    candidate when it's absent (the usual single-archive item) or names a
    file that isn't there."""
    drive_c = _scalar(meta.get("dosbox_drive_c"))
    if drive_c:
        for name in candidates:
            if name.lower() == drive_c.lower():
                return name
    return candidates[0]


def fetch_item(identifier: str) -> ArchiveItemInfo:
    """Fetch identifier's metadata and resolve which of its files to
    download. Raises NotDosItemError if it has no DOS emulator metadata,
    LookupError if it does but no file matching emulator_ext can be
    found among its files."""
    url = METADATA_URL.format(identifier=identifier)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())

    meta = data.get("metadata") or {}
    emulator = _scalar(meta.get("emulator"))
    emulator_start = _scalar(meta.get("emulator_start"))
    if not emulator or not emulator_start:
        raise NotDosItemError(f"'{identifier}' has no DOS emulator metadata - is it a DOS software item?")

    ext = (_scalar(meta.get("emulator_ext")) or "zip").lower()
    files = data.get("files") or []
    candidates = [f["name"] for f in files if f.get("name", "").lower().endswith(f".{ext}")]
    if not candidates:
        raise LookupError(f"No .{ext} file found among '{identifier}''s files")
    filename = _pick_archive(candidates, meta)

    return ArchiveItemInfo(
        identifier=identifier,
        title=_scalar(meta.get("title")),
        year=_scalar(meta.get("year")),
        emulator=emulator,
        emulator_ext=ext,
        emulator_start=emulator_start,
        download_filename=filename,
        download_url=DOWNLOAD_URL.format(identifier=identifier, filename=urllib.parse.quote(filename)),
    )
