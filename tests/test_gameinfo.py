"""Tests for dedb.gog.gameinfo - parsing a goggame-*.info's playTasks.

The playTask shapes below are modelled on real GOG DOS releases (a base +
"single player" conf pair, a choice of primary/other tasks) but carry no
game, company or product name from any of them.
"""

import json

import pytest

from dedb.convert import split_command
from dedb.gog.gameinfo import _conf_basenames, parse_profiles


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ("", []),
        ("1207658934 NET", ["1207658934", "NET"]),
        (r"-conf ..\game.conf", ["-conf", r"..\game.conf"]),
        (
            r'-conf "..\game.conf" -conf "..\game_single.conf" -noconsole -c "exit"',
            ["-conf", r"..\game.conf", "-conf", r"..\game_single.conf", "-noconsole", "-c", "exit"],
        ),
        (r'"c:\with space\run.exe" /q', [r"c:\with space\run.exe", "/q"]),
        ("has#hash inside", ["has#hash", "inside"]),  # '#' is not a comment
    ],
)
def test_split_command_keeps_backslashes_and_unquotes(arguments, expected):
    assert split_command(arguments) == expected


def test_conf_basenames_takes_the_file_after_each_conf_flag():
    args = r'-conf "..\sub\A.conf" -conf B.conf -noconsole'
    assert _conf_basenames(args) == ["A.conf", "B.conf"]


def _write_info(dir_, tasks):
    (dir_ / "goggame-0000.info").write_text(json.dumps({"playTasks": tasks}))


def test_parse_profiles_reads_file_launchable_tasks(tmp_path):
    _write_info(
        tmp_path,
        [
            {
                "name": "Play",
                "isPrimary": True,
                "category": "game",
                "path": "dosbox\\dosbox.exe",
                "arguments": r'-conf "..\game.conf" -conf "..\game_single.conf"',
                "workingDir": "dosbox",
            },
            {"name": "Support", "path": ""},  # no path -> skipped
        ],
    )

    profiles = parse_profiles(tmp_path)

    assert len(profiles) == 1
    p = profiles[0]
    assert (p.name, p.is_primary, p.category) == ("Play", True, "game")
    assert p.path == "dosbox\\dosbox.exe"
    assert p.working_dir == "dosbox"
    assert p.conf_files == ["game.conf", "game_single.conf"]


def test_parse_profiles_returns_empty_when_theres_no_info_file(tmp_path):
    assert parse_profiles(tmp_path) == []
