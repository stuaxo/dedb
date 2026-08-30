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


# --- deprecated rungog / runarchive --------------------------------


def test_rungog_warns_on_stderr_and_still_dispatches(download_dir, spy_run):
    result = CliRunner().invoke(cli, ["rungog", "tyrian_2000", "--dosbox"])

    assert result.exit_code == 0
    assert "deprecated" in result.stderr
    assert "deprecated" not in result.stdout
    assert spy_run["run"]["target"].scheme == "gog"
    assert spy_run["run"]["target"].identifier == "tyrian_2000"


def test_rungog_profile_flag_threads_through(download_dir, spy_run):
    CliRunner().invoke(cli, ["rungog", "x", "--dosbox", "--profile", "host"])

    assert spy_run["run"]["target"].profile == "host"


def test_runarchive_accepts_item_url_and_warns(download_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "dedb.archive.backend.ArchiveBackend.ensure_downloaded",
        lambda self, identifier, **kw: seen.update(identifier=identifier) or "LAYOUT",
    )
    monkeypatch.setattr(
        "dedb.archive.backend.ArchiveBackend.run",
        lambda self, target, layout, **kw: seen.update(target=target) or 0,
    )
    result = CliRunner().invoke(
        cli, ["runarchive", "https://archive.org/details/msdos_Foo", "--dosbox"]
    )

    assert result.exit_code == 0
    assert "deprecated" in result.stderr
    assert seen["identifier"] == "msdos_Foo"


def test_downloadgog_is_not_deprecated():
    result = CliRunner().invoke(cli, ["downloadgog", "--help"])

    assert "deprecated" not in result.output.lower()
