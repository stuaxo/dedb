"""Tests for dedb.backends (registry + target resolution) and the two
backend classes.

resolve() and BackendBase.local_names() use *function-local* `from
dedb.core import ...`, so tests patch the origin `dedb.core.<name>`, not a
re-imported alias.
"""

import dataclasses
from pathlib import Path

import click
import pytest

from dedb.archive.backend import ArchiveBackend
from dedb.backends import Target, resolve
from dedb.core import get_backends
from dedb.gog.backend import GogBackend

ARCHIVE_URL = "https://archive.org/details/msdos_Electro_Man_1992"


# --- registry / discovery -------------------------------------------------


def test_get_backends_registers_known_schemes():
    assert set(get_backends()) == {"gog", "archive"}


def test_get_backends_is_ordered_by_settings_apps():
    assert list(get_backends()) == ["gog", "archive"]


def test_get_backends_skips_apps_without_a_backend_module():
    # dedb.dosbox has no backend module - get_backends() must not raise.
    assert "dosbox" not in get_backends()


def test_backend_instances_are_frozen_dataclasses():
    gog = get_backends()["gog"]
    assert dataclasses.is_dataclass(type(gog))
    with pytest.raises(dataclasses.FrozenInstanceError):
        gog.scheme = "nope"


def test_backend_profile_support_flags():
    assert get_backends()["gog"].supports_profile is True
    assert get_backends()["archive"].supports_profile is False


# --- identifier_from_url ------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://archive.org/details/msdos_Electro_Man_1992",
        "https://archive.org/download/msdos_Electro_Man_1992",
        "http://www.archive.org/metadata/msdos_Electro_Man_1992",
    ],
)
def test_archive_identifier_from_url_matches(url):
    assert ArchiveBackend().identifier_from_url(url) == "msdos_Electro_Man_1992"


def test_archive_identifier_from_url_ignores_other_urls():
    assert ArchiveBackend().identifier_from_url("https://example.com/x") is None


def test_gog_has_no_url_recognition():
    assert GogBackend().identifier_from_url(ARCHIVE_URL) is None


# --- resolve(): scheme URLs -------------------------------------------


def test_resolve_scheme_url():
    assert resolve("gog://tyrian_2000") == Target("gog", "tyrian_2000", None, "gog://tyrian_2000")


def test_resolve_scheme_url_without_double_slash():
    assert resolve("gog:tyrian_2000").identifier == "tyrian_2000"


def test_resolve_profile_from_query():
    assert resolve("gog://tyrian_2000?profile=host").profile == "host"


def test_resolve_profile_flag_overrides_query():
    assert resolve("gog://tyrian_2000?profile=host", profile="client").profile == "client"


def test_resolve_preserves_identifier_case():
    assert resolve("archive://msdos_Foo").identifier == "msdos_Foo"


def test_resolve_archive_rejects_profile_query():
    with pytest.raises(click.ClickException):
        resolve("archive://msdos_Foo?profile=x")


def test_resolve_archive_rejects_profile_flag():
    with pytest.raises(click.ClickException):
        resolve("archive://msdos_Foo", profile="x")


# --- resolve(): http(s) URLs ----------------------------------------


def test_resolve_archive_item_url():
    target = resolve(ARCHIVE_URL)
    assert (target.scheme, target.identifier) == ("archive", "msdos_Electro_Man_1992")


def test_resolve_unknown_http_url_errors():
    with pytest.raises(click.ClickException, match="Don't know how to handle URL"):
        resolve("https://example.com/game")


def test_resolve_unknown_scheme_errors_not_treated_as_bare_name():
    with pytest.raises(click.ClickException, match="Unknown target scheme"):
        resolve("steam://12345")


# --- resolve(): bare names ------------------------------------------


@pytest.fixture
def local_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "downloads"
    (root / "gog" / "tyrian_2000").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: root / scheme)
    return root


def test_resolve_bare_name_hits_one_backend(local_downloads):
    assert resolve("tyrian_2000") == Target("gog", "tyrian_2000", None, "tyrian_2000")


def test_resolve_bare_name_no_hits_suggests_schemes(local_downloads):
    with pytest.raises(click.ClickException, match="gog://nope"):
        resolve("nope")


def test_resolve_bare_name_typo_suggestion(local_downloads):
    with pytest.raises(click.ClickException, match=r"Did you mean:\s+dedb run tyrian_2000"):
        resolve("tyrian2000")


def test_resolve_bare_name_abbreviation_suggestion(tmp_path, monkeypatch):
    root = tmp_path / "downloads"
    (root / "gog" / "jazz_jackrabbit_collection").mkdir(parents=True)
    (root / "gog" / "dungeon_keeper").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: root / scheme)

    with pytest.raises(click.ClickException, match=r"dedb run jazz_jackrabbit_collection"):
        resolve("jazz")  # unique prefix
    with pytest.raises(click.ClickException, match=r"dedb run dungeon_keeper"):
        resolve("keeper")  # unique substring


def test_resolve_bare_name_no_suggestion_when_nothing_close(local_downloads):
    with pytest.raises(click.ClickException) as exc:
        resolve("totally-different-xyz")
    assert "Did you mean" not in str(exc.value)


def test_resolve_bare_name_ambiguous(local_downloads):
    (local_downloads / "archive" / "tyrian_2000").mkdir(parents=True)
    with pytest.raises(click.ClickException, match="multiple backends"):
        resolve("tyrian_2000")
