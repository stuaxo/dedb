"""Tests for dedb.convert.autoexec.

SHIMS routes an autoexec line to a handler that rewrites it for
userhook.bat and says how well DOSEMU2 copes. Real DOSBox, run via -conf,
never sees the rewrites.
"""

from pathlib import Path

import pytest

from dedb.convert.autoexec import (
    Severity,
    check_autoexec_line,
    convert_autoexec,
    diagnose_autoexec,
    shim_mount,
)

# --- the single matcher ----------------------------------------------


def test_check_autoexec_line_passes_an_unrecognised_line_through():
    assert check_autoexec_line("GAME.EXE") == ("GAME.EXE", None)


def test_check_autoexec_line_fast_passes_a_blank_line():
    assert check_autoexec_line("   ") == ("   ", None)


def test_check_autoexec_line_reports_the_shim_that_matched():
    rewritten, hit = check_autoexec_line("IMGMOUNT E disk.img")

    assert rewritten == "REM IMGMOUNT E disk.img"
    assert hit is not None
    name, severity, _summary = hit
    assert (name, severity) == ("imgmount", Severity.UNSUPPORTED)


def test_overlay_mount_is_matched_before_the_plain_mount_rule():
    _rewritten, hit = check_autoexec_line('MOUNT D "..\\saves" -t overlay')

    assert hit is not None
    assert hit[0] == "overlay-mount"


# --- shim_mount -----------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('MOUNT C "GAME"', 'REM MOUNT C "GAME"'),
        ("mount c ..", "REM mount c .."),
        ("@MOUNT C GAMES", "REM @MOUNT C GAMES"),
    ],
)
def test_shim_mount_drops_the_c_drive(line: str, expected: str):
    rewritten, severity, _summary = shim_mount(
        line, drive="C", dos_path="x", working_dir=Path("/w")
    )

    assert (rewritten, severity) == (expected, Severity.UNSUPPORTED)


def test_check_autoexec_line_defaults_a_missing_working_dir_to_cwd(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    rewritten, _hit = check_autoexec_line("MOUNT D SAVES")

    assert rewritten == f"LREDIR -f D: {(tmp_path / 'SAVES').resolve()}"


def test_shim_mount_with_a_working_dir_rewrites_to_lredir(tmp_path: Path):
    rewritten, severity, _summary = shim_mount(
        "MOUNT D GAME", drive="D", dos_path="GAME", working_dir=tmp_path
    )

    assert rewritten == f"LREDIR -f D: {(tmp_path / 'GAME').resolve()}"
    assert severity is Severity.PARTIALLY_SUPPORTED


def test_shim_mount_preserves_a_leading_at(tmp_path: Path):
    rewritten, _severity, _summary = shim_mount(
        "@MOUNT D GAME", drive="D", dos_path="GAME", working_dir=tmp_path
    )

    assert rewritten == f"@LREDIR -f D: {(tmp_path / 'GAME').resolve()}"


# --- convert_autoexec (the whole autoexec) --------------------------


def test_convert_autoexec_without_working_dir_comments_out_every_mount(launcher_autoexec_lines):
    result = convert_autoexec(launcher_autoexec_lines)

    assert [line for line in result if "MOUNT" in line.upper()] == [
        'REM MOUNT C ".."',
        'REM MOUNT D "..\\cloud_saves" -t overlay',
    ]


def test_convert_autoexec_leaves_choice_untouched(launcher_autoexec_lines):
    result = convert_autoexec(launcher_autoexec_lines)

    assert "CHOICE /C123 /S Which program do you want to run?: /N" in result


def test_convert_autoexec_preserves_command_order(launcher_autoexec_lines):
    result = convert_autoexec(launcher_autoexec_lines)

    assert [line for line in result if not line.startswith("REM")] == [
        "@ECHO OFF",
        "c:",
        "CHOICE /C123 /S Which program do you want to run?: /N",
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


def test_convert_autoexec_with_working_dir_still_drops_c_and_overlay_mounts(
    tmp_path: Path, launcher_autoexec_lines
):
    result = convert_autoexec(launcher_autoexec_lines, working_dir=tmp_path)

    assert 'REM MOUNT C ".."' in result
    # The overlay mount matches its own rule before shim_mount, so it is
    # never turned into an LREDIR.
    assert 'REM MOUNT D "..\\cloud_saves" -t overlay' in result
    assert not any(line.startswith("LREDIR") for line in result)


def test_convert_autoexec_rewrites_a_secondary_mount_with_a_working_dir(tmp_path: Path):
    (line,) = convert_autoexec(["MOUNT D SAVES"], working_dir=tmp_path)

    assert line == f"LREDIR -f D: {(tmp_path / 'SAVES').resolve()}"


def test_convert_autoexec_comments_out_imgmount(launcher_autoexec_lines):
    result = convert_autoexec([*launcher_autoexec_lines, "IMGMOUNT E disk.img -t iso"])

    assert "REM IMGMOUNT E disk.img -t iso" in result


# --- diagnose_autoexec ---------------------------------------------


def test_diagnose_autoexec_reports_the_line_each_shim_rewrote(launcher_autoexec_lines):
    issues = diagnose_autoexec([*launcher_autoexec_lines, "IMGMOUNT E disk.img"])

    by_line = {(i.workaround, i.line): i for i in issues}
    assert by_line[("mount", 'MOUNT C ".."')].rewritten == 'REM MOUNT C ".."'
    assert by_line[("overlay-mount", 'MOUNT D "..\\cloud_saves" -t overlay')].rewritten.startswith(
        "REM "
    )
    assert by_line[("imgmount", "IMGMOUNT E disk.img")].rewritten == "REM IMGMOUNT E disk.img"


def test_diagnose_autoexec_tags_each_issue_with_its_severity(launcher_autoexec_lines):
    severities = {i.workaround: i.severity for i in diagnose_autoexec(launcher_autoexec_lines)}

    assert severities["mount"] is Severity.UNSUPPORTED  # MOUNT C, no working_dir
    assert severities["overlay-mount"] is Severity.UNSUPPORTED


def test_diagnose_autoexec_ignores_choice(launcher_autoexec_lines):
    assert "choice" not in {i.workaround for i in diagnose_autoexec(launcher_autoexec_lines)}


def test_diagnose_autoexec_reports_nothing_for_a_clean_autoexec():
    assert diagnose_autoexec(["@ECHO OFF", "c:", "GAME.EXE"]) == []


def test_diagnose_autoexec_with_working_dir_reports_the_lredir_translation(tmp_path: Path):
    (issue,) = diagnose_autoexec(["MOUNT D SAVES"], tmp_path)

    assert issue.workaround == "mount"
    assert issue.severity is Severity.PARTIALLY_SUPPORTED
    assert issue.rewritten == f"LREDIR -f D: {(tmp_path / 'SAVES').resolve()}"
