"""Tests for the generic URL-driven commands (`dedb run|download|import|rm`,
and the target mode of `dedb dosboxconf`).

These cover the CLI wiring only - option surface, dispatch, output, exit
codes. Target *resolution* (schemes, bare names, "did you mean") is
tested in test_backends.

Seam: patch the backend *class* method (instances are frozen dataclasses),
patch `dedb.core.settings.get_settings` at its origin, and patch helpers
the verb imports by name where the verb imports them
(`dedb.cli.remove_downloads`).
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from dedb.cli import cli
from dedb.core import Target
from dedb.core.settings import Settings
from dedb.dosbox.cli import dosboxconf


@pytest.fixture
def download_dir(tmp_path, monkeypatch):
    """Point dedb at a real (empty) download_dir so require_download_dir works."""
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    return tmp_path


@pytest.fixture
def spy_run(monkeypatch):
    """Fake GogBackend.ensure_downloaded + .run, recording the call. Set
    calls['exit_code'] to make .run return non-zero."""
    calls: dict = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda self, identifier, **kw: (
            calls.update(ensure={"identifier": identifier, **kw}) or "LAYOUT"
        ),
    )
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.run",
        lambda self, target, layout, **kw: (
            calls.update(run={"target": target, **kw}) or calls.get("exit_code", 0)
        ),
    )
    return calls


# --- run --------------------------------------------------------------


def test_run_dispatches_with_profile_and_emulator(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://tyrian_2000?profile=host", "--dosbox"])

    assert result.exit_code == 0
    assert spy_run["ensure"]["identifier"] == "tyrian_2000"
    assert spy_run["run"]["emulator"] == "dosbox"
    assert spy_run["run"]["target"].profile == "host"


def test_run_forwards_emulator_args_after_double_dash(download_dir, spy_run):
    CliRunner().invoke(cli, ["run", "gog://x", "--dosemu", "--", "-fullscreen"])

    assert spy_run["run"]["emulator"] == "dosemu"
    assert spy_run["run"]["extra_args"] == ("-fullscreen",)


def test_run_propagates_nonzero_exit(download_dir, spy_run):
    spy_run["exit_code"] = 3
    assert CliRunner().invoke(cli, ["run", "gog://x", "--dosbox"]).exit_code == 3


def test_run_requires_exactly_one_emulator(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://x"])
    assert result.exit_code == 2
    assert "exactly one of --dosbox or --dosemu" in result.output


def test_run_accepts_a_bare_local_name(tmp_path, monkeypatch, spy_run):
    (tmp_path / "gog" / "alpha").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))

    result = CliRunner().invoke(cli, ["run", "alpha", "--dosemu"])

    assert result.exit_code == 0
    assert spy_run["run"]["target"].identifier == "alpha"


# --- download / import / rm -----------------------------------------


def test_download_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda self, identifier, **kw: seen.update(identifier=identifier, **kw),
    )
    result = CliRunner().invoke(cli, ["download", "gog://x", "--keep"])

    assert result.exit_code == 0
    assert seen == {"identifier": "x", "keep": True, "refresh_metadata": False, "redownload": False}
    assert "Downloaded 'x'" in result.output


def test_import_dispatches(download_dir, monkeypatch):
    seen = {}

    # Stub with convert()'s real signature (keyword-only output_dir/force,
    # no `profile` - the profile rides on the target), so a mismatched
    # call from _do_import fails the test instead of being swallowed.
    def fake_convert(self, target, *, output_dir=None, force=False):
        seen.update(id=target.identifier, output_dir=output_dir, force=force)
        return Path("/out")

    monkeypatch.setattr("dedb.gog.backend.GogBackend.convert", fake_convert)
    result = CliRunner().invoke(cli, ["import", "gog://x", "--force"])

    assert result.exit_code == 0
    assert (seen["id"], seen["force"]) == ("x", True)
    assert "Imported 'x' -> '/out'" in result.output


def test_import_refreshconf_reconverts_a_downloaded_archive_item(download_dir, monkeypatch):
    """`import archive://<id> --refreshconf` on a downloaded item calls
    convert(force=True) with the archive backend's real signature."""
    seen = {}
    monkeypatch.setattr(
        "dedb.archive.backend.ArchiveBackend.is_downloaded", lambda self, ident: True
    )

    def fake_convert(self, target, *, output_dir=None, force=False):
        seen.update(id=target.identifier, force=force)
        return Path("/out")

    monkeypatch.setattr("dedb.archive.backend.ArchiveBackend.convert", fake_convert)
    result = CliRunner().invoke(cli, ["import", "archive://x", "--refreshconf"])

    assert result.exit_code == 0, result.output
    assert seen == {"id": "x", "force": True}


def test_download_dispatches_every_game_before_the_first_fetch(download_dir, monkeypatch):
    ids = []
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda self, identifier, **kw: ids.append(identifier),
    )
    result = CliRunner().invoke(cli, ["download", "gog://a", "gog://b"])

    assert result.exit_code == 0, result.output
    assert ids == ["a", "b"]
    assert "Downloaded 'a'" in result.output and "Downloaded 'b'" in result.output


def test_download_bad_ref_aborts_before_any_fetch(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda *a, **k: pytest.fail("must not fetch when a later arg is bad"),
    )
    result = CliRunner().invoke(cli, ["download", "gog://a", "bogus://b"])
    assert result.exit_code != 0
    assert "Unknown scheme 'bogus://'" in result.output


def test_import_output_dir_rejects_multiple_games(download_dir):
    result = CliRunner().invoke(cli, ["import", "gog://a", "gog://b", "-o", "/tmp/out"])
    assert result.exit_code == 2
    assert "--output-dir takes a single GAME" in result.output


def test_rm_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.cli.remove_downloads",
        lambda layouts, *, assume_yes: seen.update(
            names=[lo.dir.name for lo in layouts], assume_yes=assume_yes
        ),
    )
    result = CliRunner().invoke(cli, ["rm", "gog://x", "-y"])

    assert result.exit_code == 0
    assert seen == {"names": ["x"], "assume_yes": True}


def test_rm_expands_a_wildcard_and_dedups(tmp_path, monkeypatch):
    for rel in ("gog/tyrian_2000", "gog/tyrian_2k", "gog/doom", "archive/tyrian_x"):
        (tmp_path / rel).mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    seen = {}
    monkeypatch.setattr(
        "dedb.cli.remove_downloads",
        lambda layouts, *, assume_yes: seen.update(
            targets={(lo.dir.parent.name, lo.dir.name) for lo in layouts}
        ),
    )

    result = CliRunner().invoke(cli, ["rm", "gog:tyrian*", "gog://doom", "doom", "-y"])

    assert result.exit_code == 0, result.output
    assert seen["targets"] == {("gog", "tyrian_2000"), ("gog", "tyrian_2k"), ("gog", "doom")}


def test_rm_wildcard_matching_nothing_is_reported(tmp_path, monkeypatch):
    (tmp_path / "gog" / "doom").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))

    result = CliRunner().invoke(cli, ["rm", "zzz*", "-y"])
    assert result.exit_code == 0
    assert "No downloads match 'zzz*'" in result.output


def test_rm_confirms_once_for_the_whole_set(tmp_path, monkeypatch):
    for name in ("doom", "quake"):
        (tmp_path / "gog" / name / "game").mkdir(parents=True)
        (tmp_path / "gog" / name / "game" / "f").write_text("x")
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))

    result = CliRunner().invoke(cli, ["rm", "gog:*"], input="y\n")

    assert result.exit_code == 0, result.output
    assert "About to remove 2 downloads" in result.output
    assert not (tmp_path / "gog" / "doom").exists()
    assert not (tmp_path / "gog" / "quake").exists()


# --- -b/--backend component form ----------------------------------


def test_backend_option_equals_scheme_prefix(download_dir, spy_run):
    CliRunner().invoke(cli, ["run", "tyrian_2000", "-b", "gog", "--dosbox"])
    assert spy_run["run"]["target"] == Target("gog", "tyrian_2000", None, "gog://tyrian_2000")


@pytest.mark.parametrize(
    ("args", "match"),
    [
        (["run", "gog://x", "-b", "gog", "--dosbox"], "not both"),
        (["download", "x", "-b", "nope"], "Unknown backend 'nope'"),
    ],
)
def test_backend_option_errors(download_dir, args, match):
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    assert match in result.output


# --- import: --dump* / --refreshconf ------------------------------


def test_import_dumpconf_prints_only_the_conf(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [("default", "$_dpmi = (131072)\n", ["GAME.EXE"])],
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--dumpconf"])
    assert result.output == "$_dpmi = (131072)\n"


def test_import_dumpuserhook_labels_multiple_profiles(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [("default", "c1", ["A.EXE"]), ("server", "c2", ["B.EXE"])],
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--dumpuserhook"])
    assert "[default]" in result.output and "[server]" in result.output
    assert "A.EXE" in result.output and "B.EXE" in result.output


def test_import_refreshconf_skips_when_not_downloaded(download_dir, monkeypatch):
    monkeypatch.setattr("dedb.gog.backend.GogBackend.is_downloaded", lambda self, ident: False)
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.convert",
        lambda *a, **k: pytest.fail("convert() must not run"),
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--refreshconf"])
    assert result.exit_code == 0
    assert "Skipping 'x'" in result.output


# --- dedb dosboxconf: file paths vs targets ----------------------


def test_dosboxconf_missing_file_points_at_a_game(tmp_path):
    result = CliRunner().invoke(dosboxconf, [str(tmp_path / "nope.conf")])
    assert result.exit_code == 2
    assert "not an existing dosbox.conf" in result.output
    assert "gog:<id>" in result.output


@pytest.mark.parametrize(
    "args",
    [["gog://tyrian_2000"], ["gog:tyrian_2000"], ["tyrian_2000", "-b", "gog"]],
)
def test_dosboxconf_target_mode(tmp_path, monkeypatch, args):
    conf = tmp_path / "x.conf"
    conf.write_text("[sblaster]\nsbtype=sb16\n", encoding="cp437")
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.dosbox_command_line",
        lambda self, target: (["-conf", str(conf)], None),
    )
    result = CliRunner().invoke(dosboxconf, [*args, "-s"])
    assert result.exit_code == 0
    assert "sbtype=sb16" in result.output


def test_dosboxconf_archive_target_reads_the_emularity_command_line(download_dir, monkeypatch):
    """archive.org items have no dosbox.conf - dosboxconf renders the
    synthetic emularity command line instead (issues, autoexec, defaults)."""
    from datetime import datetime, timezone

    from dedb.archive.models import ArchiveMetadata
    from dedb.core import GameMetadataFile, get_backends

    layout = get_backends()["archive"].layout("msdos_Foo")
    layout.game.mkdir(parents=True)
    (layout.game / "GAME.EXE").write_text("MZ")
    metadata = ArchiveMetadata(
        identifier="msdos_Foo",
        emulator="dosbox",
        emulator_ext="zip",
        emulator_start="FOO/GAME.EXE",
        download_filename="x.zip",
        download_url="https://archive.org/download/x/x.zip",
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    layout.metadata_json.write_text(
        GameMetadataFile(
            scheme="archive", identifier="msdos_Foo", source=metadata.model_dump(mode="json")
        ).model_dump_json()
    )

    result = CliRunner().invoke(dosboxconf, ["archive://msdos_Foo"])
    assert result.exit_code == 0
    assert "[autoexec]" in result.output
    assert "GAME.EXE" in result.output
    assert "[sblaster]" in result.output


def test_dosboxconf_archive_target_needs_a_download(download_dir):
    result = CliRunner().invoke(dosboxconf, ["archive://msdos_Foo"])
    assert result.exit_code != 0
    assert "download" in result.output.lower()


# --- refreshmetadata ---------------------------------------------


@pytest.fixture
def spy_refresh(monkeypatch):
    """Record BackendBase.refresh_metadata calls as {scheme: [ids]}."""
    calls: dict = {}
    monkeypatch.setattr(
        "dedb.core.backends.BackendBase.refresh_metadata",
        lambda self, identifiers: calls.setdefault(self.scheme, []).extend(identifiers),
    )
    return calls


def _downloaded(root, *rel):
    for r in rel:
        (root / r / "game").mkdir(parents=True)
        (root / r / "game" / "GAME.EXE").write_text("MZ")


def test_refreshmetadata_no_args_covers_every_downloaded_game(tmp_path, monkeypatch, spy_refresh):
    _downloaded(tmp_path, "gog/alpha", "gog/beta", "archive/msdos_z")
    (tmp_path / "gog" / "half").mkdir()  # in local_names() but not extracted
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))

    result = CliRunner().invoke(cli, ["refreshmetadata"])

    assert result.exit_code == 0, result.output
    assert spy_refresh == {"gog": ["alpha", "beta"], "archive": ["msdos_z"]}
    assert "Refreshed metadata for 3 games" in result.output


def test_refreshmetadata_named_game_dispatches(download_dir, spy_refresh):
    _downloaded(download_dir, "gog/x")

    result = CliRunner().invoke(cli, ["refreshmetadata", "gog://x"])

    assert result.exit_code == 0, result.output
    assert spy_refresh == {"gog": ["x"]}


def test_refreshmetadata_skips_a_named_game_that_isnt_downloaded(download_dir, spy_refresh):
    result = CliRunner().invoke(cli, ["refreshmetadata", "gog://ghost"])

    assert result.exit_code == 0
    assert "Skipping gog:ghost: not downloaded" in result.output
    assert spy_refresh == {}
    assert "Refreshed metadata for 0 games" in result.output


def test_refreshmetadata_errors_on_an_unknown_ref(download_dir, spy_refresh):
    result = CliRunner().invoke(cli, ["refreshmetadata", "bogus://x"])

    assert result.exit_code != 0
    assert "Unknown scheme 'bogus://'" in result.output
    assert spy_refresh == {}


# --- the old per-backend verbs are gone -------------------------


@pytest.mark.parametrize(
    "name",
    [
        "rungog",
        "importgog",
        "dosboxconfgog",
        "rmgog",
        "runarchive",
        "downloadarchive",
        "importarchive",
        "rmarchive",
    ],
)
def test_removed_per_backend_commands(name):
    result = CliRunner().invoke(cli, [name, "--help"])
    assert result.exit_code == 2
    assert "No such command" in result.output
