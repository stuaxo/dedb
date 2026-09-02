"""Tests for dedb.core.runner: the launch helpers both backend runners
share. (Which DOSBox binary to run lives on DosboxSettings - see
test_settings.)"""

import subprocess

import click
import pytest

from dedb.core import runner
from dedb.core.layout import LayoutPaths


def test_launch_maps_missing_executable_to_a_clean_error(monkeypatch):
    def _boom(*_a, **_k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", _boom)

    with pytest.raises(click.ClickException, match="install the thing"):
        runner.launch(["nope"], missing_hint="install the thing")


def test_launch_returns_the_child_exit_code_and_passes_cwd(monkeypatch, tmp_path):
    seen = {}

    def _run(cmd, cwd=None):
        seen["cmd"], seen["cwd"] = cmd, cwd
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(subprocess, "run", _run)

    assert runner.launch(["x", "y"], cwd=tmp_path, missing_hint="_") == 3
    assert seen == {"cmd": ["x", "y"], "cwd": tmp_path}


def test_launch_verbose_echoes_the_command_with_cwd(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))

    runner.launch(["dosbox", "-conf", "a b"], cwd=tmp_path, missing_hint="_", verbose=True)

    out = capsys.readouterr().out
    assert str(tmp_path) in out
    assert "'a b'" in out  # shlex-quoted argument


class _Layout(LayoutPaths):
    def __init__(self, root):
        self.dir = root
        self.download_dir = root.parent


def test_launch_dosemu_stages_the_userhook_and_builds_the_argv(monkeypatch, tmp_path):
    layout = _Layout(tmp_path / "item")
    layout.game.mkdir(parents=True)
    userhook_src = tmp_path / "userhook_mp.bat"
    userhook_src.write_text("echo hi\n")

    seen = {}

    def _run(cmd, cwd=None):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", _run)

    rc = runner.launch_dosemu(
        layout,
        dosemu_conf=tmp_path / "dosemu.conf",
        userhook_src=userhook_src,
        extra_args=["-K", "."],
    )

    assert rc == 0
    assert (layout.game / "userhook.bat").read_text() == "echo hi\n"
    assert layout.dosemu_local.is_dir()
    cmd = seen["cmd"]
    assert cmd[:3] == ["dosemu", "-f", str(tmp_path / "dosemu.conf")]
    assert cmd[-2:] == ["-K", "."]
    assert f'$_lredir_paths = "{layout.game}"' in cmd
