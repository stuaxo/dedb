"""Tests for the generic URL-driven commands (`dedb run|download|import|rm`)
and the deprecated rungog/runarchive wrappers.

Seam: patch the backend *class* method (backend instances are frozen
dataclasses and can't be setattr'd). resolve()/BackendBase reach into
dedb.core with function-local imports, so patch `dedb.core.<name>`.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from dedb.cli import cli
from dedb.dosbox.cli import dosboxconf
from dedb.settings import Settings


@pytest.fixture
def download_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point dedb at a real (empty) download_dir so require_download_dir works."""
    monkeypatch.setattr("dedb.core.get_settings", lambda: Settings(download_dir=tmp_path))
    return tmp_path


@pytest.fixture
def spy_run(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Fake GogBackend.ensure_downloaded + .run, recording the call."""
    calls: dict = {}

    def fake_ensure(self, identifier, *, keep, refresh_metadata, redownload):
        calls["ensure"] = {
            "identifier": identifier,
            "keep": keep,
            "refresh_metadata": refresh_metadata,
            "redownload": redownload,
        }
        return "LAYOUT"

    def fake_run(self, target, layout, *, emulator, extra_args, verbose):
        calls["run"] = {
            "target": target,
            "layout": layout,
            "emulator": emulator,
            "extra_args": extra_args,
        }
        return calls.get("exit_code", 0)

    monkeypatch.setattr("dedb.gog.backend.GogBackend.ensure_downloaded", fake_ensure)
    monkeypatch.setattr("dedb.gog.backend.GogBackend.run", fake_run)
    return calls


# --- run --------------------------------------------------------------


def test_run_dispatches_to_gog_dosbox(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://tyrian_2000", "--dosbox"])

    assert result.exit_code == 0
    assert spy_run["ensure"]["identifier"] == "tyrian_2000"
    assert spy_run["run"]["emulator"] == "dosbox"
    assert spy_run["run"]["target"].scheme == "gog"


def test_run_passes_emulator_args_after_double_dash(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://x", "--dosemu", "--", "-fullscreen"])

    assert result.exit_code == 0
    assert spy_run["run"]["emulator"] == "dosemu"
    assert spy_run["run"]["extra_args"] == ("-fullscreen",)


def test_run_profile_from_url(download_dir, spy_run):
    CliRunner().invoke(cli, ["run", "gog://x?profile=host", "--dosbox"])

    assert spy_run["run"]["target"].profile == "host"


def test_run_nonzero_exit_propagates(download_dir, spy_run):
    spy_run["exit_code"] = 3
    result = CliRunner().invoke(cli, ["run", "gog://x", "--dosbox"])

    assert result.exit_code == 3


def test_run_requires_exactly_one_emulator(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://x"])

    assert result.exit_code == 2
    assert "exactly one of --dosbox or --dosemu" in result.output


def test_run_archive_rejects_profile(download_dir):
    result = CliRunner().invoke(cli, ["run", "archive://x", "--dosbox", "--profile", "p"])

    assert result.exit_code != 0
    assert "--profile" in result.output


def test_run_bare_name_resolves_to_local_download(tmp_path, monkeypatch, spy_run):
    root = tmp_path / "dl"
    (root / "gog" / "alpha").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.get_settings", lambda: Settings(download_dir=root))
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: root / scheme)

    result = CliRunner().invoke(cli, ["run", "alpha", "--dosemu"])

    assert result.exit_code == 0
    assert spy_run["run"]["target"].scheme == "gog"
    assert spy_run["run"]["target"].identifier == "alpha"


def test_run_unknown_bare_name_suggests_closest(tmp_path, monkeypatch):
    root = tmp_path / "dl"
    (root / "gog" / "tyrian_2000").mkdir(parents=True)
    monkeypatch.setattr("dedb.core.get_settings", lambda: Settings(download_dir=root))
    monkeypatch.setattr("dedb.core.get_download_dir", lambda scheme: root / scheme)

    result = CliRunner().invoke(cli, ["run", "tyrian2000", "--dosbox"])

    assert result.exit_code != 0
    assert "Did you mean:  dedb run tyrian_2000" in result.output


# --- download / import / rm ------------------------------------------


def test_download_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.ensure_downloaded",
        lambda self, identifier, **kw: seen.update(identifier=identifier, **kw),
    )
    result = CliRunner().invoke(cli, ["download", "gog://x", "--keep"])

    assert result.exit_code == 0
    assert seen["identifier"] == "x" and seen["keep"] is True
    assert "Downloaded 'x'" in result.output


def test_import_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.convert",
        lambda self, target, **kw: seen.update(target=target, **kw) or Path("/somewhere"),
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--force"])

    assert result.exit_code == 0
    assert seen["force"] is True
    assert "Imported 'x'" in result.output


def test_import_archive_rejects_profile(download_dir):
    result = CliRunner().invoke(cli, ["import", "archive://x", "--profile", "p"])

    assert result.exit_code != 0


def test_rm_dispatches(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.core.remove_download",
        lambda root, name, *, assume_yes: seen.update(root=root, name=name, assume_yes=assume_yes),
    )
    result = CliRunner().invoke(cli, ["rm", "gog://x", "-y"])

    assert result.exit_code == 0
    assert seen["name"] == "x" and seen["assume_yes"] is True
    assert seen["root"] == download_dir / "gog"


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


# --- -b/--backend component form ----------------------------------


def test_backend_option_is_equivalent_to_scheme(download_dir, spy_run):
    CliRunner().invoke(cli, ["run", "tyrian_2000", "-b", "gog", "--dosbox"])

    assert spy_run["run"]["target"].scheme == "gog"
    assert spy_run["run"]["target"].identifier == "tyrian_2000"


def test_backend_option_conflicts_with_scheme(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["run", "gog://x", "-b", "gog", "--dosbox"])

    assert result.exit_code == 2
    assert "not both" in result.output


def test_backend_option_unknown_backend(download_dir):
    result = CliRunner().invoke(cli, ["download", "x", "-b", "nope"])

    assert result.exit_code == 2
    assert "Unknown backend 'nope'" in result.output


# --- import dump / refreshconf -----------------------------------


def test_import_dumpconf(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [("default", "$_dpmi = (131072)\n", ["@ECHO OFF", "GAME.EXE"])],
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--dumpconf"])

    assert result.exit_code == 0
    assert result.output == "$_dpmi = (131072)\n"


def test_import_dumpuserhook_multi_profile_labels(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [
            ("default", "cfg1", ["A.EXE"]),
            ("server", "cfg2", ["B.EXE"]),
        ],
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--dumpuserhook"])

    assert "[default]" in result.output and "[server]" in result.output
    assert "A.EXE" in result.output and "B.EXE" in result.output


def test_import_refreshconf_skips_when_not_downloaded(download_dir, monkeypatch):
    monkeypatch.setattr("dedb.gog.backend.GogBackend.is_downloaded", lambda self, ident: False)
    called = []
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.convert", lambda self, *a, **k: called.append(1)
    )
    result = CliRunner().invoke(cli, ["import", "gog://x", "--refreshconf"])

    assert result.exit_code == 0
    assert "Skipping 'x'" in result.output
    assert not called


# --- dedb dosboxconf: file paths vs targets ----------------------


def test_dosboxconf_missing_file_hints_at_target(tmp_path):
    result = CliRunner().invoke(dosboxconf, [str(tmp_path / "nope.conf")])

    assert result.exit_code == 2
    assert "<scheme>://<id>" in result.output


def test_dosboxconf_target_mode_uses_backend(tmp_path, monkeypatch):
    conf = tmp_path / "x.conf"
    conf.write_text("[sblaster]\nsbtype=sb16\n[autoexec]\ngame.exe\n", encoding="cp437")
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.dosbox_sources", lambda self, target: ([conf], None)
    )

    result = CliRunner().invoke(dosboxconf, ["gog://tyrian_2000", "-s"])

    assert result.exit_code == 0
    assert "sbtype=sb16" in result.output


def test_dosboxconf_backend_option(tmp_path, monkeypatch):
    conf = tmp_path / "x.conf"
    conf.write_text("[gus]\ngus=true\n", encoding="cp437")
    seen = {}
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.dosbox_sources",
        lambda self, target: seen.update(identifier=target.identifier) or ([conf], None),
    )

    result = CliRunner().invoke(dosboxconf, ["tyrian_2000", "-b", "gog", "-g"])

    assert result.exit_code == 0
    assert seen["identifier"] == "tyrian_2000"


def test_dosboxconf_archive_target_has_no_conf():
    result = CliRunner().invoke(dosboxconf, ["archive://msdos_Foo"])

    assert result.exit_code != 0
    assert "no dosbox.conf" in result.output
