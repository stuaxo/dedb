"""Tests for the generic URL-driven commands (`dedb run|download|import|rm`,
and the target mode of `dedb dosboxconf`).

These cover the CLI wiring only - option surface, dispatch, output, exit
codes. Target *resolution* (schemes, bare names, "did you mean") is
tested in test_backends.

Seam: patch the backend *class* method (instances are frozen dataclasses).
resolve()/BackendBase use function-local `from dedb.core import ...`, so
patch `dedb.core.<name>`.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from dedb.backends import Target
from dedb.cli import cli
from dedb.dosbox.cli import dosboxconf
from dedb.settings import Settings


@pytest.fixture
def download_dir(tmp_path, monkeypatch):
    """Point dedb at a real (empty) download_dir so require_download_dir works."""
    monkeypatch.setattr("dedb.core.get_settings", lambda: Settings(download_dir=tmp_path))
    return tmp_path


@pytest.fixture
def spy_run(monkeypatch):
    """Fake GogBackend.ensure_downloaded + .run, recording the call. Set
    calls['exit_code'] to make .run return non-zero."""
    calls: dict = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda self, identifier, **kw: calls.update(ensure={"identifier": identifier, **kw}) or "LAYOUT",
    )
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.run",
        lambda self, target, layout, **kw: calls.update(run={"target": target, **kw})
        or calls.get("exit_code", 0),
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
    monkeypatch.setattr("dedb.core.get_settings", lambda: Settings(download_dir=tmp_path))
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: tmp_path / scheme)

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
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.convert",
        lambda self, target, **kw: seen.update(id=target.identifier, **kw) or Path("/out"),
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--force"])

    assert result.exit_code == 0
    assert (seen["id"], seen["force"]) == ("x", True)
    assert "Imported 'x' -> '/out'" in result.output


def test_rm_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.core.remove_download",
        lambda root, name, *, assume_yes: seen.update(root=root, name=name, assume_yes=assume_yes),
    )
    result = CliRunner().invoke(cli, ["rm", "gog://x", "-y"])

    assert result.exit_code == 0
    assert seen == {"root": download_dir / "gog", "name": "x", "assume_yes": True}


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


def test_dosboxconf_missing_file_points_at_target_syntax(tmp_path):
    result = CliRunner().invoke(dosboxconf, [str(tmp_path / "nope.conf")])
    assert result.exit_code == 2
    assert "<scheme>://<id>" in result.output


@pytest.mark.parametrize("args", [["gog://tyrian_2000"], ["tyrian_2000", "-b", "gog"]])
def test_dosboxconf_target_mode(tmp_path, monkeypatch, args):
    conf = tmp_path / "x.conf"
    conf.write_text("[sblaster]\nsbtype=sb16\n", encoding="cp437")
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.dosbox_sources", lambda self, target: ([conf], None)
    )
    result = CliRunner().invoke(dosboxconf, [*args, "-s"])
    assert result.exit_code == 0
    assert "sbtype=sb16" in result.output


def test_dosboxconf_archive_target_has_no_conf():
    result = CliRunner().invoke(dosboxconf, ["archive://msdos_Foo"])
    assert result.exit_code != 0
    assert "no dosbox.conf" in result.output


# --- the old per-backend verbs are gone -------------------------


@pytest.mark.parametrize(
    "name",
    [
        "rungog", "importgog", "dosboxconfgog", "rmgog",
        "runarchive", "downloadarchive", "importarchive", "rmarchive",
    ],
)
def test_removed_per_backend_commands(name):
    result = CliRunner().invoke(cli, [name, "--help"])
    assert result.exit_code == 2
    assert "No such command" in result.output
