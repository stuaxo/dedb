"""Tests for dedb.dosbox.inspector, focused on the --issues report.

The issues report reuses the autoexec shims as its detector (see
test_autoexec for the detector itself), so what it lists always matches
what actually lands in userhook.bat.
"""

from pathlib import Path

from click.testing import CliRunner

from dedb.dosbox.cli import dosboxconf
from dedb.dosbox.inspector import inspect, inspect_command_line

_MIXED_AUTOEXEC = "[autoexec]\nIMGMOUNT E disk.img\nMOUNT C ..\nCHOICE /C:YN Continue?\ngame.exe\n"


def test_inspect_issues_default_is_the_compact_set_format(write_conf):
    conf = write_conf(_MIXED_AUTOEXEC)

    out = inspect([conf], issues=True)

    assert out == "\n".join(
        [
            "[issues]",
            "Commands unsupported:",
            "'imgmount'",
            "'mount'",
        ]
    )


def test_inspect_issues_bands_are_ordered_most_severe_first(write_conf, tmp_path: Path):
    # IMGMOUNT -> unsupported; a secondary MOUNT with a working_dir ->
    # partially supported (rewritten to LREDIR).
    conf = write_conf("[autoexec]\nIMGMOUNT E disk.img\nMOUNT D SAVES\ngame.exe\n")

    out = inspect([conf], issues=True, working_dir=tmp_path)

    assert out.index("Commands unsupported:") < out.index("Commands partially supported:")


def test_inspect_issues_verbose_shows_each_rewrite(write_conf):
    conf = write_conf(_MIXED_AUTOEXEC)

    out = inspect([conf], issues=True, verbose=True)

    assert "unsupported (" in out
    assert "imgmount: IMGMOUNT" in out
    assert "IMGMOUNT E disk.img  ->  REM IMGMOUNT E disk.img" in out


def test_inspect_issues_only_omits_the_other_sections(write_conf, launcher_profile_conf):
    conf = write_conf(launcher_profile_conf)

    out = inspect([conf], issues=True)

    assert out.startswith("[issues]")
    assert "[autoexec]" not in out
    assert "[sblaster]" not in out


def test_inspect_default_view_still_excludes_issues(write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)

    out = inspect([conf])

    assert "[issues]" not in out
    assert "[autoexec]" in out


def test_inspect_issues_reports_none_for_a_clean_conf(write_conf):
    conf = write_conf("[autoexec]\nGAME.EXE\n")

    assert inspect([conf], issues=True) == "[issues]\n(none)"
    assert inspect([conf], issues=True, verbose=True) == "[issues]\n(none)"


def test_inspect_command_line_reads_config_set_and_autoexec_from_an_argv():
    """An emularity-style / -conf-less command line renders the same way a
    dosbox.conf does - config -set folds into the sections, plain -c
    commands are the autoexec."""
    out = inspect_command_line(
        [
            "-c",
            "config -set sblaster sbtype=sb16",
            "-c",
            "MOUNT C .",
            "-c",
            "GAME.EXE",
        ],
        sblaster=True,
        autoexec=True,
    )

    assert "[sblaster]\nsbtype=sb16" in out
    assert "[autoexec]\nMOUNT C .\nGAME.EXE" in out


def test_inspect_command_line_reports_issues_from_the_synthetic_autoexec():
    out = inspect_command_line(["-c", "IMGMOUNT E disk.img", "-c", "GAME.EXE"], issues=True)

    assert "Commands unsupported:" in out
    assert "'imgmount'" in out


def test_dosboxconf_issues_flag(write_conf, launcher_profile_conf):
    conf = write_conf(launcher_profile_conf)

    result = CliRunner().invoke(dosboxconf, [str(conf), "--issues"])

    assert result.exit_code == 0
    assert "Commands unsupported:" in result.output
    assert "'overlay-mount'" in result.output
    # compact by default - no per-line rewrites
    assert "->" not in result.output


def test_dosboxconf_issues_verbose_flag(write_conf, launcher_profile_conf):
    conf = write_conf(launcher_profile_conf)

    result = CliRunner().invoke(dosboxconf, [str(conf), "--issues", "-v"])

    assert result.exit_code == 0
    assert 'MOUNT C ".."  ->  REM MOUNT C ".."' in result.output
