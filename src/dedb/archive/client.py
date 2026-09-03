"""archive.org access via the ``internetarchive`` library.

A DOSBox-playable "software" item carries three metadata fields dedb needs:
``emulator`` (e.g. "dosbox"), ``emulator_ext`` (the game archive's extension,
usually "zip") and ``emulator_start`` (the file to run, relative to the
archive root). See https://archive.org/details/msdos_Electro_Man_1992.
"""

import re
import urllib.parse
from pathlib import Path

from internetarchive import download as ia_download
from internetarchive import get_item, search_items
from requests.exceptions import RequestException

from ..core import DownloadError
from ..core.client import BaseClient
from .models import ArchiveFavorite, ArchiveItemInfo

DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

# archive.org DOS software collections; a favorited DOS game is in both
# "fav-<user>" and one of these, which is how get_list() filters.
MSDOS_COLLECTIONS = ("softwarelibrary_msdos", "softwarelibrary_msdos_games")

# What the internetarchive calls raise on a network/server failure.
FETCH_ERRORS = (RequestException,)

_ITEM_URL_RE = re.compile(
    r"^https?://(?:www\.)?archive\.org/(?:details|download|metadata)/([^/?#]+)"
)


class NotDosItemError(LookupError):
    """An item lacks the ``emulator``/``emulator_start`` metadata of a
    DOSBox-playable item."""


def parse_identifier(value: str) -> str:
    """The bare identifier from a bare id or a full archive.org item URL."""
    match = _ITEM_URL_RE.match(value)
    return match.group(1) if match else value


def _scalar(value: object) -> str | None:
    """First value of an archive.org metadata field (a str, or a list)."""
    if isinstance(value, list):
        return value[0] if value else None
    return value  # type: ignore[return-value]


def _resolve_drive_c_archive(archive_names: list[str], meta: dict) -> str:
    """Which ``emulator_ext``-matching file to mount as C:.

    A multi-archive item (e.g. shareware alongside registered) names it in
    ``dosbox_drive_c``, as archive.org's own loader does; else use the first.
    """
    drive_c = _scalar(meta.get("dosbox_drive_c"))
    if drive_c:
        for name in archive_names:
            if name.lower() == drive_c.lower():
                return name
    return archive_names[0]


class ArchiveClient(BaseClient):
    default_name = "favorites"

    def has_default_list(self) -> bool:
        return False

    def download(self, identifier: str, filename: str, dest_dir: Path) -> None:
        """Fetch one file from an item into dest_dir (flat), retrying transient failures."""
        errors = ia_download(
            identifier, files=[filename], destdir=str(dest_dir), no_directory=True, retries=3
        )
        if errors:
            raise DownloadError(
                f"Could not download '{filename}' from archive.org item '{identifier}'"
            )

    def get_list(
        self, name: str | None = None, *, dos_only: bool = True, **kwargs
    ) -> list[ArchiveFavorite]:
        """List a user's archive.org favorites (the ``fav-<username>`` collection), title-sorted.

        :param dos_only: if True, only items also in a DOS software collection.
        :raises ValueError: if name (username) is not provided.
        :raises LookupError: archive.org reports no such user, or no favorites.
        :raises requests.exceptions.RequestException: network failure.
        """
        if name is None:
            raise ValueError("username is required for archive.org favorites")

        query = f"collection:fav-{name}"
        if dos_only:
            query += " AND collection:(" + " OR ".join(MSDOS_COLLECTIONS) + ")"

        def _year(doc: dict) -> str | None:
            value = _scalar(doc.get("year"))
            return str(value) if value is not None else None

        results = search_items(
            query,
            fields=["identifier", "title", "year"],
            sorts=["titleSorter asc"],
        )
        favorites = [
            ArchiveFavorite(
                identifier=doc["identifier"],
                title=_scalar(doc.get("title")),
                year=_year(doc),
            )
            for doc in results
            if doc.get("identifier")
        ]
        if not favorites:
            hint = " (does this user have any favorited MS-DOS items?)" if dos_only else ""
            raise LookupError(f"No favorites found for archive.org user '{name}'{hint}")

        return favorites


def fetch_item(identifier: str) -> ArchiveItemInfo:
    """Resolve an item's metadata and the file to download.

    :raises NotDosItemError: no DOS emulator metadata.
    :raises LookupError: no file matches ``emulator_ext``.
    """
    item = get_item(identifier)
    meta = item.metadata

    emulator = _scalar(meta.get("emulator"))
    emulator_start = _scalar(meta.get("emulator_start"))
    if not emulator or not emulator_start:
        raise NotDosItemError(
            f"'{identifier}' has no DOS emulator metadata - is it a DOS software item?"
        )

    ext = (_scalar(meta.get("emulator_ext")) or "zip").lower()
    archive_names = [f["name"] for f in item.files if f.get("name", "").lower().endswith(f".{ext}")]
    if not archive_names:
        raise LookupError(f"No .{ext} file found among '{identifier}''s files")
    filename = _resolve_drive_c_archive(archive_names, meta)

    return ArchiveItemInfo(
        identifier=identifier,
        title=_scalar(meta.get("title")),
        year=_scalar(meta.get("year")),
        emulator=emulator,
        emulator_ext=ext,
        emulator_start=emulator_start,
        download_filename=filename,
        download_url=DOWNLOAD_URL.format(
            identifier=identifier, filename=urllib.parse.quote(filename)
        ),
    )
