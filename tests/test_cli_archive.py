"""Tests for `dedb lsarchive` and the archive.org favorites client.

The autouse _isolate_dedb_config fixture (conftest) already points
settings at a throwaway config dir. `lsarchive` does a function-local
`from .client import favorite_items`, so tests patch it on the client
module, not on dedb.archive.cli.
"""

import json
import urllib.error
import urllib.parse

import pytest
from click.testing import CliRunner

from dedb import core
from dedb.archive import client as archive_client
from dedb.archive.models import ArchiveFavorite
from dedb.cli import cli
from dedb.settings import Settings, load_settings, save_archive_favorites_user

FAVES = [
    ArchiveFavorite(identifier="msdos_Electro_Man_1992", title="Electro Man", year="1992"),
    ArchiveFavorite(identifier="msdos_Zzt", title="ZZT"),
]


@pytest.fixture
def configured_user(monkeypatch):
    monkeypatch.setattr(
        "dedb.core.get_settings",
        lambda: Settings(archive={"favorites_user": "someuser"}),
    )


@pytest.fixture
def fake_favorites(monkeypatch):
    calls = {}

    def _fake(username, *, dos_only=True):
        calls["username"] = username
        calls["dos_only"] = dos_only
        return FAVES

    monkeypatch.setattr(archive_client, "favorite_items", _fake)
    return calls


def test_lsarchive_lists_configured_users_favorites(configured_user, fake_favorites):
    result = CliRunner().invoke(cli, ["lsarchive"])

    assert result.exit_code == 0
    assert fake_favorites == {"username": "someuser", "dos_only": True}
    lines = result.output.splitlines()
    assert lines[0].startswith("archive:msdos_Electro_Man_1992")
    assert lines[0].endswith("Electro Man (1992)")
    assert lines[1].startswith("archive:msdos_Zzt")
    assert lines[1].endswith("ZZT")


def test_lsarchive_names_only(configured_user, fake_favorites):
    result = CliRunner().invoke(cli, ["lsarchive", "-1"])

    assert result.output.splitlines() == [
        "archive:msdos_Electro_Man_1992",
        "archive:msdos_Zzt",
    ]


def test_lsarchive_all_drops_the_dos_filter(configured_user, fake_favorites):
    CliRunner().invoke(cli, ["lsarchive", "--all"])

    assert fake_favorites["dos_only"] is False


def test_lsarchive_user_flag_overrides_the_setting(configured_user, fake_favorites):
    CliRunner().invoke(cli, ["lsarchive", "--user", "override"])

    assert fake_favorites["username"] == "override"


def test_lsarchive_prompts_when_unconfigured_and_saves(fake_favorites):
    load_settings()  # write the packaged default so there's a file to edit
    core.get_settings.cache_clear()

    result = CliRunner().invoke(cli, ["lsarchive"], input="prompteduser\ny\n")

    assert result.exit_code == 0
    assert fake_favorites["username"] == "prompteduser"
    assert load_settings().archive.favorites_user == "prompteduser"


def test_lsarchive_prompts_but_can_decline_to_save(fake_favorites):
    load_settings()
    core.get_settings.cache_clear()

    result = CliRunner().invoke(cli, ["lsarchive"], input="prompteduser\nn\n")

    assert result.exit_code == 0
    assert fake_favorites["username"] == "prompteduser"
    assert load_settings().archive.favorites_user is None


def test_lsarchive_reports_a_network_failure(configured_user, monkeypatch):
    def _boom(username, *, dos_only=True):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(archive_client, "favorite_items", _boom)
    result = CliRunner().invoke(cli, ["lsarchive"])

    assert result.exit_code == 1
    assert "Could not reach archive.org" in result.output


def test_lsarchive_reports_an_empty_favorites_collection(configured_user, monkeypatch):
    def _empty(username, *, dos_only=True):
        raise LookupError("No favorites found for archive.org user 'someuser'")

    monkeypatch.setattr(archive_client, "favorite_items", _empty)
    result = CliRunner().invoke(cli, ["lsarchive"])

    assert result.exit_code == 1
    assert "No favorites found" in result.output


# --- client.favorite_items -------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


@pytest.fixture
def capture_search(monkeypatch):
    seen = {}

    def _fake_urlopen(url, timeout=None):
        seen["url"] = url
        return _FakeResponse(
            {"response": {"docs": [{"identifier": "msdos_Foo", "title": "Foo", "year": 1993}]}}
        )

    monkeypatch.setattr(archive_client.urllib.request, "urlopen", _fake_urlopen)
    return seen


def test_favorite_items_queries_the_fav_collection_filtered_to_dos(capture_search):
    items = archive_client.favorite_items("bob")

    query = urllib.parse.unquote_plus(capture_search["url"])
    assert "collection:fav-bob" in query
    assert "softwarelibrary_msdos" in query
    assert items == [ArchiveFavorite(identifier="msdos_Foo", title="Foo", year="1993")]


def test_favorite_items_all_omits_the_dos_collection_filter(capture_search):
    archive_client.favorite_items("bob", dos_only=False)

    query = urllib.parse.unquote_plus(capture_search["url"])
    assert "collection:fav-bob" in query
    assert "softwarelibrary_msdos" not in query


def test_favorite_items_raises_lookup_error_on_no_docs(monkeypatch):
    monkeypatch.setattr(
        archive_client.urllib.request,
        "urlopen",
        lambda url, timeout=None: _FakeResponse({"response": {"docs": []}}),
    )
    with pytest.raises(LookupError):
        archive_client.favorite_items("nobody")


def test_save_archive_favorites_user_is_idempotent_and_preserves_comments():
    load_settings()
    save_archive_favorites_user("first")
    save_archive_favorites_user("second")

    from dedb import settings

    text = settings.SETTINGS_PATH.read_text()
    uncommented = [ln for ln in text.splitlines() if ln.strip().startswith("favorites_user")]
    assert uncommented == ['favorites_user = "second"']
    assert "# dedb configuration." in text  # comments preserved
    assert load_settings().archive.favorites_user == "second"
