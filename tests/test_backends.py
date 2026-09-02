"""Tests for dedb.core.backends: the backend registry and target resolution.

resolve() and BackendBase reach into dedb.core with *function-local*
imports, so tests patch the origin `dedb.core.<name>`, not a re-imported
alias.
"""

import dataclasses

import click
import pytest

from dedb.archive.backend import ArchiveBackend
from dedb.archive.models import ArchiveFavorite
from dedb.core import Target, get_backends, long_target, resolve, short_target
from dedb.gog.backend import GogBackend
from dedb.gog.models import OwnedGame

ARCHIVE_URL = "https://archive.org/details/msdos_Electro_Man_1992"


# --- target reference formatting ----------------------------------------


def test_short_and_long_target_spellings():
    assert short_target("archive", "msdos_Foo") == "archive:msdos_Foo"
    assert long_target("archive", "msdos_Foo") == "archive://msdos_Foo"


@pytest.mark.parametrize(
    "reference",
    [
        ArchiveFavorite(identifier="msdos_Foo").target,
        OwnedGame(gamename="tyrian_2000", product_id="1").target,
        Target("gog", "x", None, "x").url,
    ],
)
def test_model_target_references_round_trip_through_resolve(reference):
    # Everything that formats a `<scheme>:<id>` reference must be something
    # resolve() accepts back.
    scheme, _, identifier = reference.partition(":")
    assert resolve(reference) == Target(scheme, identifier.lstrip("/"), None, reference)


# --- registry -----------------------------------------------------------


def test_registry_holds_both_backends_in_settings_order():
    # Calling get_backends() also exercises the "app has no backend module"
    # skip (dedb.dosbox) - a masked ImportError there would blow up here.
    assert list(get_backends()) == ["gog", "archive"]
    assert "dosbox" not in get_backends()


def test_backends_are_frozen_dataclasses_carrying_their_flags():
    gog, archive = get_backends()["gog"], get_backends()["archive"]
    assert dataclasses.is_dataclass(type(gog)) and dataclasses.is_dataclass(type(archive))
    assert (gog.supports_profile, archive.supports_profile) == (True, False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        gog.scheme = "nope"


# --- identifier_from_url ---------------------------------------------


@pytest.mark.parametrize(
    ("backend", "url", "expected"),
    [
        (ArchiveBackend(), "https://archive.org/details/msdos_X", "msdos_X"),
        (ArchiveBackend(), "https://archive.org/download/msdos_X", "msdos_X"),
        (ArchiveBackend(), "http://www.archive.org/metadata/msdos_X", "msdos_X"),
        (ArchiveBackend(), "https://example.com/msdos_X", None),
        (GogBackend(), ARCHIVE_URL, None),  # GOG owns no URL shape
    ],
)
def test_identifier_from_url(backend, url, expected):
    assert backend.identifier_from_url(url) == expected


# --- resolve(): URLs -------------------------------------------------


@pytest.mark.parametrize(
    ("value", "kwargs", "expected"),
    [
        ("gog://tyrian_2000", {}, ("gog", "tyrian_2000", None)),
        ("gog:tyrian_2000", {}, ("gog", "tyrian_2000", None)),  # no slashes
        ("gog:///tyrian_2000", {}, ("gog", "tyrian_2000", None)),  # empty authority
        ("gog://x?profile=host", {}, ("gog", "x", "host")),  # profile from query
        ("gog:///x?profile=host", {}, ("gog", "x", "host")),  # slashes + query
        ("gog://x?profile=host", {"profile": "cli"}, ("gog", "x", "cli")),  # flag wins
        ("archive://msdos_Foo", {}, ("archive", "msdos_Foo", None)),  # case kept
        (ARCHIVE_URL, {}, ("archive", "msdos_Electro_Man_1992", None)),  # pasted URL
    ],
)
def test_resolve_urls(value, kwargs, expected):
    target = resolve(value, **kwargs)
    assert (target.scheme, target.identifier, target.profile) == expected


@pytest.mark.parametrize(
    ("value", "kwargs", "match"),
    [
        ("archive://msdos_Foo?profile=x", {}, "profile"),
        ("archive://msdos_Foo", {"profile": "x"}, "profile"),
        ("https://example.com/game", {}, "Don't know how to handle URL"),
        ("steam://12345", {}, "Unknown scheme"),  # not treated as a bare name
    ],
)
def test_resolve_url_errors(value, kwargs, match):
    with pytest.raises(click.ClickException, match=match):
        resolve(value, **kwargs)


# --- resolve(): bare names -----------------------------------------


@pytest.fixture
def local_downloads(tmp_path, monkeypatch):
    """A gog/ download dir holding a few games."""
    root = tmp_path / "downloads"
    for name in ("tyrian_2000", "jazz_jackrabbit_collection", "dungeon_keeper"):
        (root / "gog" / name).mkdir(parents=True)
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: root / scheme)
    return root


def test_bare_name_resolves_when_downloaded_under_one_backend(local_downloads):
    assert resolve("tyrian_2000") == Target("gog", "tyrian_2000", None, "tyrian_2000")


def test_bare_name_ambiguous_across_backends(local_downloads):
    (local_downloads / "archive" / "tyrian_2000").mkdir(parents=True)
    with pytest.raises(click.ClickException, match="multiple backends"):
        resolve("tyrian_2000")


@pytest.mark.parametrize(
    ("typed", "suggestion"),
    [
        ("tyrian2000", "tyrian_2000"),  # difflib near-miss
        ("jazz", "jazz_jackrabbit_collection"),  # unique prefix
        ("keeper", "dungeon_keeper"),  # unique substring
        ("totally-different", None),  # nothing close
    ],
)
def test_bare_name_miss_suggests_closest(local_downloads, typed, suggestion):
    with pytest.raises(click.ClickException) as exc:
        resolve(typed)
    message = str(exc.value)
    assert "gog://" in message  # always offers the scheme form
    if suggestion:
        assert f"dedb run {suggestion}" in message
    else:
        assert "Did you mean" not in message
