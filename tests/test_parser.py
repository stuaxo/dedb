"""Tests for dedb.dosbox.parser.

Covers parsing a single dosbox.conf and merging several, using generic
conf text (see conftest.py) rather than files from any specific game.
"""

from pathlib import Path

import pytest

from dedb.dosbox.parser import parse_dosbox_conf, parse_dosbox_confs


def test_parses_sections_excluding_autoexec(write_conf, base_profile_conf):
    path = write_conf(base_profile_conf)

    config, _autoexec = parse_dosbox_conf(path)

    assert config["sdl"] == {"fullscreen": "false", "output": "surface"}
    assert config["dosbox"] == {"memsize": "16"}
    assert config["cpu"] == {"cycles": "auto"}
    assert "autoexec" not in config


def test_autoexec_commands_are_ordered(write_conf, base_profile_conf):
    path = write_conf(base_profile_conf)

    _config, autoexec = parse_dosbox_conf(path)

    assert autoexec == ["MOUNT C GAME", "game.exe"]


def test_no_value_line_differs_from_empty_value_line(write_conf):
    """A bare command (no "=") must stay bare; a "KEY=" line must keep
    its trailing "=". Collapsing the two would turn a MOUNT command into
    a malformed one."""
    path = write_conf(
        """
[autoexec]
MOUNT C GAME
SET PATH=
"""
    )

    _config, autoexec = parse_dosbox_conf(path)

    assert autoexec == ["MOUNT C GAME", "SET PATH="]


def test_option_names_keep_case(write_conf):
    """DOS commands are case sensitive. ConfigParser lowercases option
    names by default; parse_dosbox_conf must turn that off."""
    path = write_conf(
        """
[autoexec]
SET PATH=C:\\GAME
CHOICE /C12
"""
    )

    _config, autoexec = parse_dosbox_conf(path)

    assert autoexec == ["SET PATH=C:\\GAME", "CHOICE /C12"]


def test_reads_cp437_encoding(tmp_path: Path):
    """dosbox.conf may contain CP437 box-drawing characters. Byte 0xB2 is
    the dark shade block (U+2593) in CP437, but a different character in
    UTF-8 and Latin-1 - reading with the wrong codec would produce the
    wrong character rather than raise."""
    path = tmp_path / "dosbox.conf"
    path.write_bytes(b"[autoexec]\nECHO \xb2\n")

    _config, autoexec = parse_dosbox_conf(path)

    assert autoexec == ["ECHO ▓"]


def test_merge_overrides_later_files_win(write_conf, base_profile_conf, variant_profile_conf):
    base = write_conf(base_profile_conf)
    variant = write_conf(variant_profile_conf)

    config, _autoexec = parse_dosbox_confs([base, variant])

    assert config["sdl"]["fullscreen"] == "true"
    assert config["cpu"]["cycles"] == "max"


def test_merge_keeps_keys_only_the_base_sets(write_conf, base_profile_conf, variant_profile_conf):
    base = write_conf(base_profile_conf)
    variant = write_conf(variant_profile_conf)

    config, _autoexec = parse_dosbox_confs([base, variant])

    assert config["sdl"]["output"] == "surface"
    assert config["dosbox"]["memsize"] == "16"


def test_merge_concatenates_autoexec_in_file_order(write_conf, base_profile_conf, variant_profile_conf):
    base = write_conf(base_profile_conf)
    variant = write_conf(variant_profile_conf)

    _config, autoexec = parse_dosbox_confs([base, variant])

    assert autoexec == ["MOUNT C GAME", "game.exe", "setup.exe"]


@pytest.mark.parametrize("order", [0, 1])
def test_merge_order_determines_the_winner(write_conf, order: int):
    """Whichever file is listed last wins per key, regardless of which
    file that is."""
    conf_a = write_conf("[cpu]\ncycles=auto\n")
    conf_b = write_conf("[cpu]\ncycles=max\n")
    files = [conf_a, conf_b] if order == 0 else [conf_b, conf_a]
    expected = "max" if order == 0 else "auto"

    config, _autoexec = parse_dosbox_confs(files)

    assert config["cpu"]["cycles"] == expected
