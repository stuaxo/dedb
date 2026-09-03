"""Tests for dedb.convert.converter: the parser, models and shims wired
together, matching what the importdosbox command does.
"""

from pathlib import Path

import click
import pytest

from dedb.convert.converter import build, build_from_parsed, convert


def test_build_from_parsed_is_the_shared_seam_for_conf_and_argv():
    """build() and dedb.convert.cmdline.build_from_argv both feed a parsed
    (section_dict, autoexec_lines) pair through this one step."""
    target, userhook_lines = build_from_parsed(
        {"cpu": {"cycles": "max"}, "sdl": {"fullscreen": "true"}},
        ["MOUNT C .", "game.exe"],
    )

    assert target.X_fullscreen is True
    assert target.cpuspeed == 0
    assert userhook_lines == ["REM MOUNT C .", "game.exe"]  # no working_dir -> MOUNT commented


def test_build_merges_profiles_into_a_single_config(
    write_conf, base_profile_conf, variant_profile_conf
):
    base = write_conf(base_profile_conf)
    variant = write_conf(variant_profile_conf)

    target, _userhook_lines = build([base, variant])

    assert target.X_fullscreen is True  # set only in the variant profile
    assert target.cpuspeed == 0  # "max" cycles, from the variant profile
    assert target.dpmi == 131072  # memsize=16, set only in the base profile, floored


def test_build_applies_shims_to_the_merged_autoexec(write_conf, launcher_profile_conf):
    conf = write_conf(launcher_profile_conf)

    _target, userhook_lines = build([conf])

    assert 'REM MOUNT C ".."' in userhook_lines
    assert "CHOICE /C123 /S Which program do you want to run?: /N" in userhook_lines  # untouched


def test_build_converts_a_secondary_mount_to_lredir(tmp_path: Path, write_conf):
    conf = write_conf("[autoexec]\nMOUNT D SAVES\n")
    working_dir = tmp_path / "work"
    working_dir.mkdir()

    _target, userhook_lines = build([conf], working_dir=working_dir)

    assert userhook_lines == [f"LREDIR -f D: {(working_dir / 'SAVES').resolve()}"]


def test_convert_writes_dosemu_conf_and_userhook(tmp_path: Path, write_conf, launcher_profile_conf):
    conf = write_conf(launcher_profile_conf)
    output_dir = tmp_path / "out"

    convert([conf], output_dir)

    dosemu_conf = (output_dir / "dosemu.conf").read_text()
    assert "$_dpmi = (131072)" in dosemu_conf

    userhook = (output_dir / "userhook.bat").read_text(encoding="cp437")
    assert "GAME.EXE" in userhook


def test_convert_refuses_to_overwrite_without_force(tmp_path: Path, write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    with pytest.raises(click.ClickException):
        convert([conf], output_dir)


def test_convert_overwrites_with_force(tmp_path: Path, write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    convert([conf], output_dir, force=True)

    assert (output_dir / "dosemu.conf").exists()


def test_convert_accepts_custom_filenames(tmp_path: Path, write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)
    output_dir = tmp_path / "out"

    convert(
        [conf],
        output_dir,
        dosemu_filename="dosemu_variant.conf",
        userhook_filename="userhook_variant.bat",
    )

    assert (output_dir / "dosemu_variant.conf").exists()
    assert (output_dir / "userhook_variant.bat").exists()
