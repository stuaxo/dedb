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

from .models import ArchiveFavorite, ArchiveItemInfo

METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
SEARCH_URL = "https://archive.org/advancedsearch.php"

# archive.org's DOS software collections. A favorited item keeps every
# collection it belongs to in its (multi-valued) "collection" field, so
# an item that is both favorited and a DOS game carries "fav-<user>" and
# one of these - which is how favorite_items() filters to MS-DOS.
MSDOS_COLLECTIONS = ("softwarelibrary_msdos", "softwarelibrary_msdos_games")

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


def favorite_items(username: str, *, dos_only: bool = True, timeout: int = 20) -> list[ArchiveFavorite]:
    """List the items in ``username``'s public favorites (the
    ``fav-<username>`` collection archive.org creates for every account),
    ordered by title. With dos_only (the default), restrict the query to
    items that are also in a DOS software collection.
    Raises urllib.error.URLError on a network failure, or LookupError if
    archive.org reports no such user / an empty favorites collection."""
    query = f"collection:fav-{username}"
    if dos_only:
        query += " AND collection:(" + " OR ".join(MSDOS_COLLECTIONS) + ")"

    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "year"),
        ("sort[]", "titleSorter asc"),
        ("rows", "1000"),
        ("page", "1"),
        ("output", "json"),
    ]
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read())

    docs = (data.get("response") or {}).get("docs") or []
    if not docs:
        hint = " (does this user have any favorited MS-DOS items?)" if dos_only else ""
        raise LookupError(f"No favorites found for archive.org user '{username}'{hint}")

    def _year(doc: dict) -> str | None:
        value = _scalar(doc.get("year"))
        return str(value) if value is not None else None

    return [
        ArchiveFavorite(
            identifier=doc["identifier"],
            title=_scalar(doc.get("title")),
            year=_year(doc),
        )
        for doc in docs
        if doc.get("identifier")
    ]


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
