"""Tests for dedb.shims.autoexec.

Shims rewrite one line of a game's autoexec for userhook.bat. Real
DOSBox, run via -conf, never sees them.
"""

from pathlib import Path

import pytest

from dedb.shims.autoexec import (
    autoexec_shims,
    choice_shim,
    mount_lredir_shim,
    resolve_mounts,
    unsupported_command,
    unsupported_mount_option,
)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("CHOICE /C123 /S Pick one: /N", "CHOICE Pick one:"),
        ("choice /c12", "choice"),
        ("@CHOICE /C12", "@CHOICE"),
        ("GAME.EXE", "GAME.EXE"),
    ],
)
def test_choice_shim(line: str, expected: str):
    assert choice_shim(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('MOUNT C "GAME"', 'REM MOUNT C "GAME"'),
        ("mount c ..", "REM mount c .."),
        ("MOUNT D GAME", None),  # asserted separately: resolves to an absolute path
        ("GAME.EXE", "GAME.EXE"),
    ],
)
def test_mount_lredir_shim(tmp_path: Path, line: str, expected: str | None):
    shim = mount_lredir_shim(tmp_path)

    result = shim(line)

    if expected is not None:
        assert result == expected
    else:
        assert result == f"LREDIR -f D: {(tmp_path / 'GAME').resolve()}"


def test_mount_lredir_shim_preserves_leading_at(tmp_path: Path):
    shim = mount_lredir_shim(tmp_path)

    result = shim("@MOUNT D GAME")

    assert result == f"@LREDIR -f D: {(tmp_path / 'GAME').resolve()}"


def test_resolve_mounts_ignores_imgmount_and_flagged_mounts(tmp_path: Path):
    autoexec = [
        'MOUNT C ".."',
        "MOUNT D GAME",
        "IMGMOUNT E disk.img",
        "MOUNT -u D",
    ]

    resolved = resolve_mounts(autoexec, tmp_path)

    assert [(m.drive, m.dos_path) for m in resolved] == [("C", ".."), ("D", "GAME")]
    assert resolved[1].host_path == (tmp_path / "GAME").resolve()


@pytest.mark.parametrize(
    ("command", "line", "expected"),
    [
        ("mount", "MOUNT C GAME", "REM MOUNT C GAME"),
        ("mount", "@MOUNT C GAME", "REM @MOUNT C GAME"),
        ("mount", "mount c game", "REM mount c game"),
        ("mount", "GAME.EXE", "GAME.EXE"),
        ("imgmount", "IMGMOUNT D disk.img", "REM IMGMOUNT D disk.img"),
    ],
)
def test_unsupported_command(command: str, line: str, expected: str):
    shim = unsupported_command(command)

    assert shim(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('MOUNT D "..\\cloud_saves" -t overlay', 'REM MOUNT D "..\\cloud_saves" -t overlay'),
        ("MOUNT D GAME", "MOUNT D GAME"),
        ("GAME.EXE", "GAME.EXE"),
    ],
)
def test_unsupported_mount_option(line: str, expected: str):
    shim = unsupported_mount_option("overlay")

    assert shim(line) == expected


def test_autoexec_shims_without_working_dir_comments_out_all_mounts(launcher_autoexec_lines):
    result = autoexec_shims(launcher_autoexec_lines)

    mount_lines = [line for line in result if "MOUNT" in line.upper()]
    assert mount_lines == [
        'REM MOUNT C ".."',
        'REM MOUNT D "..\\cloud_saves" -t overlay',
    ]


def test_autoexec_shims_without_working_dir_strips_choice_flags(launcher_autoexec_lines):
    result = autoexec_shims(launcher_autoexec_lines)

    assert "CHOICE Which program do you want to run?:" in result


def test_autoexec_shims_without_working_dir_preserves_command_order(launcher_autoexec_lines):
    result = autoexec_shims(launcher_autoexec_lines)

    assert [line for line in result if not line.startswith(("REM", "CHOICE"))] == [
        "@ECHO OFF",
        "c:",
        "if errorlevel 3 goto exit",
        "if errorlevel 2 goto edit",
        "if errorlevel 1 goto game",
        ":game",
        "GAME.EXE",
        "goto exit",
        ":edit",
        "EDITOR.EXE",
        ":exit",
        "exit",
    ]


def test_autoexec_shims_with_working_dir_still_comments_out_c_and_overlay_mounts(
    tmp_path: Path, launcher_autoexec_lines
):
    result = autoexec_shims(launcher_autoexec_lines, tmp_path)

    assert 'REM MOUNT C ".."' in result
    # The overlay mount is commented out before mount_lredir_shim runs,
    # so it is never converted to an LREDIR call.
    assert 'REM MOUNT D "..\\cloud_saves" -t overlay' in result
    assert not any(line.startswith("LREDIR") for line in result)
