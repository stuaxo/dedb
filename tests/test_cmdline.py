"""Tests for dedb.convert.cmdline: building the DOSBox model from a
`dosbox` command line (the form archive.org / emularity stores) instead
of a dosbox.conf.

The argvs here are modelled on the shape of emularity launch parameters -
repeatable `-c` commands, a `-conf`, host-side flags, a trailing program -
but no game name appears. Negative cases tweak one token of a working
argv.
"""

from pathlib import Path

import pytest

from dedb.convert.cmdline import (
    build_from_argv,
    parse_dosbox_argv,
    parse_dosbox_command_line,
)


@pytest.mark.parametrize(
    ("argv", "config", "autoexec"),
    [
        pytest.param(
            ["-c", "config -set sdl fullscreen=true", "-c", "config -set cpu cycles=max"],
            {"sdl": {"fullscreen": "true"}, "cpu": {"cycles": "max"}},
            [],
            id="config-set folds into the section dict",
        ),
        pytest.param(
            ["-set", "sdl fullscreen=true"],
            {"sdl": {"fullscreen": "true"}},
            [],
            id="dosbox-staging -set option",
        ),
        pytest.param(
            ["-c", "config -set cpu cycles max"],
            {"cpu": {"cycles": "max"}},
            [],
            id="space-separated prop value",
        ),
        pytest.param(
            ["-c", "config -set cpu cycles fixed 3000"],
            {"cpu": {"cycles": "fixed 3000"}},
            [],
            id="multi-token value kept whole",
        ),
        pytest.param(
            ["-c", "mount c c:\\dosgames", "-c", "c:", "-c", "cd doom", "-c", "doom.exe"],
            {},
            ["mount c c:\\dosgames", "c:", "cd doom", "doom.exe"],
            id="DOS commands pass through as autoexec, in order",
        ),
        pytest.param(
            [
                "-c",
                "config -set cpu cycles=max",
                "-c",
                "mount c .",
                "-c",
                "config -set sdl fullscreen=true",
                "-c",
                "game.exe",
            ],
            {"cpu": {"cycles": "max"}, "sdl": {"fullscreen": "true"}},
            ["mount c .", "game.exe"],
            id="config and DOS commands interleaved keep their own order",
        ),
        pytest.param(
            ["-fullscreen", "-c", "game.exe"],
            {"sdl": {"fullscreen": "true"}},
            ["game.exe"],
            id="-fullscreen is a config item",
        ),
        pytest.param(
            ["doom.exe"],
            {},
            ["doom.exe"],
            id="a bare trailing program is an autoexec line",
        ),
        pytest.param(
            ["c:\\games\\doom\\doom.exe", "-warp"],
            {},
            ["c:\\games\\doom\\doom.exe -warp"],
            id="trailing program keeps its arguments",
        ),
    ],
)
def test_parse_dosbox_argv(argv: list[str], config: dict, autoexec: list[str]):
    assert parse_dosbox_argv(argv) == (config, autoexec)


def test_host_side_flags_are_recognised_and_dropped():
    result = parse_dosbox_command_line(
        ["-noconsole", "-exit", "-machine", "svga_s3", "-c", "game.exe"]
    )

    assert result.autoexec == ["game.exe"]
    assert result.ignored == ["-noconsole", "-exit", "-machine", "svga_s3"]


def test_config_set_for_a_key_not_in_the_model_is_still_folded_but_flagged():
    """pydantic silently drops an unknown section/key today; the command
    line reports it so a caller can see it was understood but not carried
    across."""
    result = parse_dosbox_command_line(["-c", "config -set sdl priority=higher"])

    assert result.config == {"sdl": {"priority": "higher"}}
    assert result.unmodelled == [("sdl", "priority")]


def test_conf_file_is_merged_then_overridden_by_argv(write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)  # memsize=16, cycles=auto, autoexec MOUNT C GAME

    config, autoexec = parse_dosbox_argv(
        ["-conf", str(conf), "-c", "config -set cpu cycles=max", "-c", "extra.exe"]
    )

    assert config["dosbox"]["memsize"] == "16"  # untouched, from the conf
    assert config["cpu"]["cycles"] == "max"  # argv wins over the conf's "auto"
    assert autoexec == ["MOUNT C GAME", "game.exe", "extra.exe"]  # conf first, then argv -c


def test_noautoexec_drops_the_conf_autoexec_but_keeps_argv_commands(write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)

    _config, autoexec = parse_dosbox_argv(["-conf", str(conf), "-noautoexec", "-c", "run.exe"])

    assert autoexec == ["run.exe"]


def test_relative_conf_paths_resolve_against_base_dir(write_conf, base_profile_conf):
    conf = write_conf(base_profile_conf)

    config, _autoexec = parse_dosbox_argv(["-conf", conf.name], base_dir=conf.parent)

    assert config["dosbox"]["memsize"] == "16"


def test_build_from_argv_folds_config_set_into_the_dosemu_conf():
    target, _userhook = build_from_argv(
        ["-c", "config -set sdl fullscreen=true", "-c", "config -set cpu cycles=3000"]
    )

    assert target.X_fullscreen is True
    assert target.cpuspeed == 3000


def test_build_from_argv_converts_the_autoexec():
    _target, userhook_lines = build_from_argv(["-c", "mount c .", "-c", "doom.exe"])

    assert "REM mount c ." in userhook_lines  # MOUNT with no working_dir is commented out
    assert "doom.exe" in userhook_lines


def test_build_from_argv_matches_the_equivalent_conf(write_conf):
    conf = write_conf("[sdl]\nfullscreen=true\n\n[cpu]\ncycles=max\n")

    from dedb.convert.converter import build

    conf_target, _ = build([conf])
    argv_target, _ = build_from_argv(
        ["-c", "config -set sdl fullscreen=true", "-c", "config -set cpu cycles=max"]
    )

    assert argv_target.model_dump() == conf_target.model_dump()


def test_build_from_argv_resolves_a_secondary_mount_with_a_working_dir(tmp_path: Path):
    working_dir = tmp_path / "work"
    working_dir.mkdir()

    _target, userhook_lines = build_from_argv(["-c", "MOUNT D SAVES"], working_dir=working_dir)

    assert userhook_lines == [f"LREDIR -f D: {(working_dir / 'SAVES').resolve()}"]
