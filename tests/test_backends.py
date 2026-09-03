"""Tests for dedb.core.backends: the backend registry and target resolution.

resolve() / BackendBase call helpers as `<module>.<name>()`, so tests
patch the origin - `dedb.core.settings.get_settings`,
`dedb.core.downloads.require_download_dir` - not the `dedb.core` re-export.
"""

import dataclasses
import json

import pytest

from dedb.archive.backend import ArchiveBackend
from dedb.archive.models import ArchiveFavorite
from dedb.core import (
    GameRefError,
    Target,
    complete_target,
    get_backends,
    long_target,
    resolve,
    resolve_game,
    short_target,
)
from dedb.core.settings import Settings
from dedb.gog.backend import GogBackend
from dedb.gog.models import GOGGame

ARCHIVE_URL = "https://archive.org/details/msdos_Electro_Man_1992"


# --- target reference formatting ----------------------------------------


def test_short_and_long_target_spellings():
    assert short_target("archive", "msdos_Foo") == "archive:msdos_Foo"
    assert long_target("archive", "msdos_Foo") == "archive://msdos_Foo"


@pytest.mark.parametrize(
    "reference",
    [
        ArchiveFavorite(identifier="msdos_Foo").target,
        GOGGame(gamename="tyrian_2000", product_id="1").target,
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


# --- BackendBase.run / .convert templates ----------------------------


@pytest.mark.parametrize(
    ("emulator", "expected_fn"),
    [("dosbox", "run_dosbox"), ("dosemu", "run_dosemu")],
)
def test_run_dispatches_to_the_runner_module(monkeypatch, emulator, expected_fn):
    import dedb.gog.runner as gog_runner

    seen = {}

    def _record(name):
        def _fn(*args):
            seen["call"] = (name, args)
            return 7

        return _fn

    for name in ("run_dosbox", "run_dosemu"):
        monkeypatch.setattr(gog_runner, name, _record(name))

    target = Target("gog", "x", "server", "gog://x?profile=server")
    rc = GogBackend().run(target, "LAYOUT", emulator=emulator, extra_args=["-fs"], verbose=True)

    assert rc == 7
    assert seen["call"] == (expected_fn, ("LAYOUT", target, ["-fs"], True))


@pytest.mark.parametrize("emulator", ["dosbox", "dosemu"])
def test_cmdline_builds_via_the_runner_module(monkeypatch, tmp_path, emulator):
    import dedb.gog.runner as gog_runner

    root = tmp_path / "gog" / "x"
    (root / "game").mkdir(parents=True)
    (root / "game" / "GAME.EXE").touch()  # is_downloaded() -> True
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    monkeypatch.setattr(
        gog_runner, "dosbox_conf_argv", lambda lyt, tgt: (["-conf", "a.conf"], root)
    )
    monkeypatch.setattr(gog_runner, "dosemu_conf_path", lambda lyt, tgt: root / "dosemu" / "d.conf")
    monkeypatch.setattr(
        "dedb.core.settings.DosboxSettings.get_dosbox_binary", lambda self: "dosbox-staging"
    )

    cmd, cwd = GogBackend().cmdline(Target("gog", "x", None, "gog://x"), emulator=emulator)

    if emulator == "dosbox":
        assert cmd == ["dosbox-staging", "-conf", "a.conf"]
        assert cwd == root
    else:
        assert cmd[0] == "dosemu" and str(root / "dosemu" / "d.conf") in cmd
        assert cwd is None


def test_convert_writes_via_the_import_hook_and_returns_the_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("dedb.core.downloads.require_download_dir", lambda scheme: tmp_path)

    seen = {}
    monkeypatch.setattr(
        "dedb.archive.importer.import_archive_game",
        lambda layout, output_dir, *, force: seen.update(name=layout.name, force=force),
    )

    target = Target("archive", "msdos_X", None, "archive://msdos_X")
    dest = ArchiveBackend().convert(target, force=True)

    assert seen == {"name": "msdos_X", "force": True}
    assert dest == tmp_path / "msdos_X" / "dosemu"


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
    with pytest.raises(GameRefError, match=match):
        resolve(value, **kwargs)


# --- resolve_game(): the -b/--backend shorthand --------------------


def test_resolve_game_backend_flag_is_a_scheme_prefix():
    assert resolve_game("tyrian_2000", "gog") == resolve("gog://tyrian_2000")
    # no --backend: plain resolve() (a scheme URL still works)
    assert resolve_game("gog://x") == resolve("gog://x")


@pytest.mark.parametrize(
    ("value", "backend", "match"),
    [
        ("gog://x", "gog", "not both"),  # URL *and* --backend
        ("x", "steam", "Unknown backend"),
    ],
)
def test_resolve_game_backend_flag_errors(value, backend, match):
    with pytest.raises(GameRefError, match=match):
        resolve_game(value, backend)


# --- resolve(): bare names -----------------------------------------


@pytest.fixture
def local_downloads(tmp_path, monkeypatch):
    """A gog/ download dir holding a few games."""
    root = tmp_path / "downloads"
    for name in ("tyrian_2000", "jazz_jackrabbit_collection", "dungeon_keeper"):
        (root / "gog" / name).mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=root))
    return root


def test_bare_name_resolves_when_downloaded_under_one_backend(local_downloads):
    assert resolve("tyrian_2000") == Target("gog", "tyrian_2000", None, "tyrian_2000")


def test_bare_name_ambiguous_across_backends(local_downloads):
    (local_downloads / "archive" / "tyrian_2000").mkdir(parents=True)
    with pytest.raises(GameRefError, match="multiple backends"):
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
    with pytest.raises(GameRefError) as exc:
        resolve(typed)
    message = str(exc.value)
    assert "gog://" in message  # always offers the scheme form
    if suggestion:
        assert f"dedb run {suggestion}" in message
    else:
        assert "Did you mean" not in message


# --- shell completion --------------------------------------------------


@pytest.fixture
def local_catalogue(tmp_path, monkeypatch):
    """A gog/ download, plus a GOG owned-games cache and an archive.org
    metadata cache - the local data completion draws on."""
    root = tmp_path / "downloads"
    (root / "gog" / "tyrian_2000").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=root))

    owned = tmp_path / "owned_games_cache.json"
    owned.write_text(
        json.dumps(
            [
                {"gamename": "bio_menace", "product_id": "1"},
                {"gamename": "tyrian_2000", "product_id": "2"},
            ]
        )
    )
    monkeypatch.setattr("dedb.gog.client.OWNED_GAMES_CACHE_PATH", owned)

    archive_cache = tmp_path / "archive_metadata_cache.json"
    archive_cache.write_text(json.dumps({"msdos_Electro_Man_1992": {"title": "Electro Man"}}))
    monkeypatch.setattr("dedb.archive.metadata.CACHE_PATH", archive_cache)
    return root


def _values(items):
    return [i.value for i in items]


def test_complete_target_bare_offers_scheme_prefixes_and_qualified_ids(local_catalogue):
    values = _values(complete_target(""))
    assert "gog:" in values and "archive:" in values
    assert "gog:bio_menace" in values  # from the owned-games cache
    assert "gog:tyrian_2000" in values  # download + cache, listed once
    assert values.count("gog:tyrian_2000") == 1
    assert "archive:msdos_Electro_Man_1992" in values  # from the metadata cache


def test_complete_target_scheme_prefix_filters_to_that_backend(local_catalogue):
    values = _values(complete_target("gog:b"))
    assert values == ["gog:bio_menace"]


def test_complete_target_tolerates_the_double_slash_form(local_catalogue):
    assert _values(complete_target("gog://tyr")) == ["gog:tyrian_2000"]


def test_complete_target_with_backend_completes_bare_ids(local_catalogue):
    assert _values(complete_target("bio", backend="gog")) == ["bio_menace"]


def test_complete_target_never_raises_without_a_catalogue(monkeypatch, tmp_path):
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    monkeypatch.setattr("dedb.gog.client.OWNED_GAMES_CACHE_PATH", tmp_path / "nope.json")
    monkeypatch.setattr("dedb.archive.metadata.CACHE_PATH", tmp_path / "nope.json")
    assert _values(complete_target("gog:")) == []
    assert _values(complete_target("")) == ["gog:", "archive:"]
