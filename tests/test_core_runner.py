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


def test_launch_dry_run_prints_a_bare_command_and_skips_subprocess(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))

    rc = runner.launch(["dosbox", "-conf", "a b"], cwd=tmp_path, missing_hint="_", dry_run=True)

    assert rc == 0
    out = capsys.readouterr().out
    assert not out.startswith("$ ")  # bare, shell-pasteable
    assert out.strip() == f"cd {tmp_path} && dosbox -conf 'a b'"


class _Layout(LayoutPaths):
    def __init__(self, root):
        self.dir = root
        self.download_dir = root.parent


def test_launch_dosemu_stages_the_userhook_and_builds_the_argv(monkeypatch, tmp_path):
    layout = _Layout(tmp_path / "item")
    layout.game.mkdir(parents=True)
    (layout.game / "userhook.bat").write_text("stale\n")  # left by an older dedb
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
        extra_args=["-fullscreen"],
    )

    assert rc == 0
    # staged into the dedb-owned hook dir, under a fixed name, NOT in the game dir
    assert (layout.userhook_dir / "userhook.bat").read_text() == "echo hi\n"
    assert not (layout.game / "userhook.bat").exists()
    assert layout.dosemu_local.is_dir()
    cmd = seen["cmd"]
    assert cmd[:3] == ["dosemu", "-f", str(tmp_path / "dosemu.conf")]
    assert cmd[-1] == "-fullscreen"
    assert f'$_lredir_paths = "{layout.dir}"' in cmd
    k = cmd.index("-K")
    assert cmd[k : k + 4] == ["-K", str(layout.userhook_dir), "-E", "USERHOOK.BAT"]


def test_launch_dosemu_dry_run_does_not_stage_the_userhook(monkeypatch, tmp_path, capsys):
    layout = _Layout(tmp_path / "item")
    layout.game.mkdir(parents=True)
    userhook_src = tmp_path / "userhook.bat"
    userhook_src.write_text("echo hi\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))

    rc = runner.launch_dosemu(
        layout, dosemu_conf=tmp_path / "dosemu.conf", userhook_src=userhook_src, dry_run=True
    )

    assert rc == 0
    assert not (layout.game / "userhook.bat").exists()
    assert not layout.userhook_dir.exists()
    assert not layout.dosemu_local.exists()
    assert f"dosemu -f {tmp_path / 'dosemu.conf'}" in capsys.readouterr().out
