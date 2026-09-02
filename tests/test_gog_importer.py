"""Tests for dedb.gog.importer.import_gog_game - turning a downloaded
game's launch profile(s) into DOSEMU2 config pair(s).

The goggame-*.info shapes are modelled on real GOG DOS releases but carry
no game, company or product name from any of them.
"""

import json

import click
import pytest

from dedb.gog.importer import import_gog_game
from dedb.gog.layout import GogLayout


def _extracted(tmp_path, base_profile_conf, *, confs=("dosbox.conf",), info_tasks=None):
    layout = GogLayout(tmp_path, "x")
    layout.game.mkdir(parents=True)
    for name in confs:
        (layout.game / name).write_text(base_profile_conf, encoding="cp437")
    if info_tasks is not None:
        (layout.game / "goggame-0000.info").write_text(json.dumps({"playTasks": info_tasks}))
    return layout


def test_legacy_game_with_no_goggame_info_writes_the_default_pair(tmp_path, base_profile_conf):
    layout = _extracted(tmp_path, base_profile_conf)

    result = import_gog_game(layout)

    assert list(result) == ["default"]
    assert (layout.dosemu / "dosemu.conf").is_file()
    assert (layout.dosemu / "userhook.bat").is_file()


def test_refuses_an_existing_output_dir_without_force(tmp_path, base_profile_conf):
    layout = _extracted(tmp_path, base_profile_conf)
    layout.dosemu.mkdir(parents=True)

    with pytest.raises(click.ClickException, match="already exists"):
        import_gog_game(layout)
    import_gog_game(layout, force=True)  # force overwrites


def test_writes_one_pair_per_launch_profile(tmp_path, base_profile_conf):
    layout = _extracted(
        tmp_path,
        base_profile_conf,
        confs=("primary.conf", "server.conf"),
        info_tasks=[
            {
                "name": "Play",
                "isPrimary": True,
                "path": "d/dosbox.exe",
                "arguments": "-conf primary.conf",
            },
            {"name": "Multiplayer Host", "path": "d/dosbox.exe", "arguments": "-conf server.conf"},
        ],
    )

    result = import_gog_game(layout)

    assert set(result) == {"default", "multiplayer_host"}
    assert (layout.dosemu / "dosemu.conf").is_file()  # the primary profile
    assert (layout.dosemu / "dosemu_multiplayer_host.conf").is_file()
