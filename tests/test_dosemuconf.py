"""Tests for `dedb dosemuconf` - the DOSEMU2-side mirror of `dosboxconf`.

Conf-path mode runs the real conversion (dedb.convert); game-ref mode
patches GogBackend.build (the seam, like test_cli_verbs).
"""

import pytest
from click.testing import CliRunner

from dedb.core.settings import Settings
from dedb.dosemu.cli import dosemuconf

SB_CONF = """
[sblaster]
sbtype=sb16
sbbase=220
[autoexec]
MOUNT C .
C:
GAME.EXE
"""


@pytest.fixture
def download_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    return tmp_path


def _conf(write_conf):
    return str(write_conf(SB_CONF))


def test_default_shows_conf_then_userhook(write_conf):
    result = CliRunner().invoke(dosemuconf, [_conf(write_conf)])

    assert result.exit_code == 0
    assert "$_sb_base = (0x220)" in result.output  # from model_dump_dosemurc
    assert "GAME.EXE" in result.output  # from userhook.bat


def test_conf_flag_shows_only_the_dosemu_conf(write_conf):
    result = CliRunner().invoke(dosemuconf, [_conf(write_conf), "--conf"])

    assert "$_sb_base = (0x220)" in result.output
    assert "GAME.EXE" not in result.output


def test_userhook_flag_shows_only_the_userhook(write_conf):
    result = CliRunner().invoke(dosemuconf, [_conf(write_conf), "--userhook"])

    assert "GAME.EXE" in result.output
    assert "$_sb_base" not in result.output


def test_issues_flag_matches_dosboxconf(write_conf, launcher_profile_conf):
    conf = str(write_conf(launcher_profile_conf))

    plain = CliRunner().invoke(dosemuconf, [conf, "--issues"])
    verbose = CliRunner().invoke(dosemuconf, [conf, "--issues", "-v"])

    assert plain.exit_code == 0
    assert "'choice'" in plain.output
    assert "->" not in plain.output
    assert "->" in verbose.output


def test_missing_conf_points_at_a_game(tmp_path):
    result = CliRunner().invoke(dosemuconf, [str(tmp_path / "nope.conf")])

    assert result.exit_code == 2
    assert "not an existing dosbox.conf" in result.output
    assert "gog:<id>" in result.output


def test_game_mode_single_profile_has_no_label_header(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [("default", "$_dpmi = (131072)\n", ["GAME.EXE"])],
    )
    result = CliRunner().invoke(dosemuconf, ["gog:x"])

    assert result.output == "$_dpmi = (131072)\n\nGAME.EXE\n"
    assert "[default]" not in result.output


def test_game_mode_multi_profile_labels_each_block(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.build",
        lambda self, target: [("default", "c1", ["A.EXE"]), ("server", "c2", ["B.EXE"])],
    )
    result = CliRunner().invoke(dosemuconf, ["gog:x", "--conf"])

    assert "[default]\nc1" in result.output
    assert "[server]\nc2" in result.output


def test_backend_component_form(download_dir, monkeypatch):
    seen = {}

    def fake_build(self, target):
        seen["id"] = target.identifier
        return [("default", "c", [])]

    monkeypatch.setattr("dedb.gog.backend.GogBackend.build", fake_build)
    CliRunner().invoke(dosemuconf, ["tyrian_2000", "-b", "gog"])

    assert seen["id"] == "tyrian_2000"


def test_rejects_two_game_refs(download_dir):
    result = CliRunner().invoke(dosemuconf, ["gog://a", "gog://b"])

    assert result.exit_code == 2
    assert "single game" in result.output


def test_cmdline_game_mode_prints_the_dosemu_command(download_dir, monkeypatch):
    monkeypatch.setattr(
        "dedb.gog.backend.GogBackend.cmdline",
        lambda self, target, **kw: (
            ["dosemu", "-f", "d.conf", "-K", "hook", "-E", "USERHOOK.BAT"],
            None,
        ),
    )
    result = CliRunner().invoke(dosemuconf, ["gog:x", "--cmdline"])

    assert result.exit_code == 0
    assert result.output.strip() == "dosemu -f d.conf -K hook -E USERHOOK.BAT"


def test_cmdline_rejects_conf_paths(write_conf):
    result = CliRunner().invoke(dosemuconf, [str(write_conf("[sdl]\n")), "--cmdline"])

    assert result.exit_code == 2
    assert "needs a game reference" in result.output
