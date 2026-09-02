"""Tests for the archive.org backend's own logic - what to fetch, which
file to boot, how to launch it.

The only thing stubbed is the one real network call the code makes
(``internetarchive.get_item`` / ``search_items``). Those stubs return
*real* archive.org responses captured once into tests/fixtures/archive/
and replayed here, so the code under test still runs against the actual
shape of archive.org data. Negative cases are derived by tweaking a
field of that captured data, not by hand-building a fake.
"""

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click
import pytest
from internetarchive import get_session
from internetarchive.item import Item

from dedb.archive import client as archive_client
from dedb.archive import downloader
from dedb.archive.client import _pick_archive, favorite_items, fetch_item
from dedb.archive.downloader import ArchiveDownloader, _safe_extract
from dedb.archive.importer import autoexec_commands
from dedb.archive.models import ArchiveFavorite, ArchiveMetadata

FIXTURES = Path(__file__).parent / "fixtures" / "archive"
DOS_ITEM_ID = "msdos_Electro_Man_1992"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# --- fetch_item: resolving what to download, against a real item ----------


@pytest.fixture
def stub_get_item(monkeypatch):
    """Replace get_item() with one returning a real Item built offline from
    the captured metadata of msdos_Electro_Man_1992, with optional
    per-test overrides to its `metadata` / `files`."""
    session = get_session()

    def _install(*, metadata=None, extra_files=()):
        raw = _load("item_electro_man_1992.json")
        raw["metadata"].update(metadata or {})
        raw["files"].extend(extra_files)
        item = Item(session, raw["metadata"]["identifier"], raw)
        monkeypatch.setattr(archive_client, "get_item", lambda ident: item)
        return item

    return _install


def test_fetch_item_resolves_launch_fields_and_the_download_file(stub_get_item):
    stub_get_item()

    info = fetch_item(DOS_ITEM_ID)

    assert info.emulator == "dosbox"
    assert info.emulator_start == "ElectroM/EM.EXE"
    assert info.emulator_ext == "zip"
    assert info.download_filename == "Electro_Man_1992.zip"
    assert info.download_url.endswith(f"/download/{DOS_ITEM_ID}/Electro_Man_1992.zip")


def test_fetch_item_rejects_an_item_with_no_dos_emulator_metadata(stub_get_item):
    item = stub_get_item()
    del item.metadata["emulator"]  # an ordinary, non-emulated archive.org item

    with pytest.raises(archive_client.NotDosItemError):
        fetch_item(DOS_ITEM_ID)


def test_fetch_item_defaults_a_missing_ext_to_zip(stub_get_item):
    item = stub_get_item()
    del item.metadata["emulator_ext"]

    assert fetch_item(DOS_ITEM_ID).download_filename == "Electro_Man_1992.zip"


def test_fetch_item_raises_when_no_file_matches_the_declared_ext(stub_get_item):
    stub_get_item(metadata={"emulator_ext": "img"})  # declared, but the item ships a .zip

    with pytest.raises(LookupError, match=r"No \.img file"):
        fetch_item(DOS_ITEM_ID)


# --- _pick_archive: choosing between several bundled archives ------------
#
# Pure function; the args below are the real metadata field and real
# archive.org filename patterns (a shareware build shipped next to the
# registered one).


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({}, "shareware.zip"),  # no hint -> first
        ({"dosbox_drive_c": "registered.zip"}, "registered.zip"),
        ({"dosbox_drive_c": "REGISTERED.ZIP"}, "registered.zip"),  # case-insensitive
        ({"dosbox_drive_c": ["registered.zip"]}, "registered.zip"),  # multi-valued field
        ({"dosbox_drive_c": "gone.zip"}, "shareware.zip"),  # hint names a missing file
    ],
)
def test_pick_archive(meta, expected):
    assert _pick_archive(["shareware.zip", "registered.zip"], meta) == expected


# --- autoexec_commands: the synthetic [autoexec] -----------------------


@pytest.mark.parametrize(
    ("emulator_start", "expected"),
    [
        ("ElectroM/EM.EXE", ["MOUNT C .", "C:", "CD ElectroM", "EM.EXE"]),  # the real fixture value
        ("GAME.EXE", ["MOUNT C .", "C:", "GAME.EXE"]),  # runnable at the root
        ("a/b/GAME.EXE", ["MOUNT C .", "C:", "CD a\\b", "GAME.EXE"]),
        ("a\\b\\GAME.EXE", ["MOUNT C .", "C:", "CD a\\b", "GAME.EXE"]),  # already backslashed
    ],
)
def test_autoexec_commands(emulator_start, expected):
    assert autoexec_commands(emulator_start) == expected


# --- _safe_extract: the zip-slip guard --------------------------------


def test_safe_extract_writes_members_under_dest(tmp_path):
    archive = tmp_path / "game.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("GAME/RUN.EXE", "MZ")

    _safe_extract(archive, tmp_path / "game")

    assert (tmp_path / "game" / "GAME" / "RUN.EXE").read_text() == "MZ"


def test_safe_extract_refuses_a_member_that_escapes_dest(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.txt", "pwned")

    with pytest.raises(click.ClickException, match="outside"):
        _safe_extract(archive, tmp_path / "game")
    assert not (tmp_path / "escaped.txt").exists()


# --- ArchiveDownloader._prepare: item-type guards --------------------


@pytest.fixture
def stub_metadata(stub_get_item, monkeypatch):
    """Route ArchiveDownloader's get_metadata through the real fetch_item
    against the captured item (so the ArchiveMetadata is shaped by real
    code), with metadata overrides applied first."""

    def _install(*, metadata=None, extra_files=()):
        stub_get_item(metadata=metadata, extra_files=extra_files)
        monkeypatch.setattr(
            downloader,
            "get_metadata",
            lambda ident, refresh=False: ArchiveMetadata(
                **fetch_item(ident).model_dump(), fetched_at=datetime.now(timezone.utc)
            ),
        )

    return _install


def _prepare(tmp_path):
    from dedb.archive.layout import GameLayout

    return ArchiveDownloader()._prepare(GameLayout(tmp_path, DOS_ITEM_ID), refresh=False)


def test_prepare_returns_the_resolved_metadata(tmp_path, stub_metadata):
    stub_metadata()
    assert _prepare(tmp_path).download_filename == "Electro_Man_1992.zip"


def test_prepare_rejects_a_non_dosbox_item(tmp_path, stub_metadata):
    stub_metadata(metadata={"emulator": "scummvm"})
    with pytest.raises(click.ClickException, match="not DOSBox"):
        _prepare(tmp_path)


def test_prepare_rejects_a_non_zip_archive(tmp_path, stub_metadata):
    # A real .7z-shipping item: the metadata's ext matches a real file.
    stub_metadata(
        metadata={"emulator_ext": "7z"},
        extra_files=[{"name": "Electro_Man_1992.7z", "format": "7z"}],
    )
    with pytest.raises(click.ClickException, match=r"only \.zip"):
        _prepare(tmp_path)


# --- favorite_items: query building + doc -> model mapping --------------


@pytest.fixture
def stub_search(monkeypatch):
    """Replace search_items() with one that records its arguments and
    replays captured real result docs."""
    seen = {}
    docs = _load("search_favorites.json")

    def _fake(query, *, fields=None, sorts=None):
        seen.update(query=query, fields=fields, sorts=sorts)
        return iter(docs)

    monkeypatch.setattr(archive_client, "search_items", _fake)
    return seen


@pytest.mark.parametrize("dos_only", [True, False])
def test_favorite_items_filters_to_dos_collections_only_when_asked(stub_search, dos_only):
    favorite_items("bob", dos_only=dos_only)

    assert "collection:fav-bob" in stub_search["query"]
    assert ("softwarelibrary_msdos" in stub_search["query"]) is dos_only


def test_favorite_items_maps_real_docs_and_stringifies_the_year(stub_search):
    first, *_ = favorite_items("bob")

    assert first == ArchiveFavorite(
        identifier="msdos_100000_Pyramid_1988", title="$100,000 Pyramid", year="1988"
    )
    assert first.target == "archive:msdos_100000_Pyramid_1988"


def test_favorite_items_raises_lookup_error_when_the_search_is_empty(monkeypatch):
    monkeypatch.setattr(
        archive_client, "search_items", lambda query, *, fields=None, sorts=None: iter([])
    )
    with pytest.raises(LookupError):
        favorite_items("nobody")
