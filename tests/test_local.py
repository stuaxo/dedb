"""Tests for the LocalGame each backend assembles for one of its
downloads (BackendBase.local_game / iter_local_games).

Builds real download trees under a tmp download_dir - an extracted
goggame-*.info and a written metadata.json - and asserts the LocalGame
the backend derives from them. The goggame-*.info shapes carry no real
game, company or product name (see tests/conftest.py).
"""

import json
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

import pytest

from dedb.archive.backend import ArchiveBackend
from dedb.core import GameMetadataFile, LaunchProfile
from dedb.core.settings import Settings
from dedb.gog.backend import GogBackend
from dedb.gog.layout import GogLayout


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    root = tmp_path / "downloads"
    root.mkdir()
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=root))
    return root


# --- GOG -----------------------------------------------------------------


def _gog_download(
    root: Path, name: str, base_profile_conf: str, *, info_tasks=None, converted=False
):
    layout = GogLayout(root / "gog", name)
    layout.game.mkdir(parents=True)
    for conf in ("primary.conf", "server.conf"):
        (layout.game / conf).write_text(base_profile_conf, encoding="cp437")
    if info_tasks is not None:
        (layout.game / "goggame-0000.info").write_text(json.dumps({"playTasks": info_tasks}))
    if converted:
        layout.dosemu.mkdir(parents=True)
        layout.dosemu_conf.write_text("$_h\n")
    return layout


def test_gog_local_game_reads_launch_profiles_and_flags_from_metadata(downloads, base_profile_conf):
    layout = _gog_download(
        downloads,
        "sample_dos_game",
        base_profile_conf,
        info_tasks=[
            {
                "name": "Play",
                "isPrimary": True,
                "path": "d/dosbox.exe",
                "arguments": "-conf primary.conf",
            },
            {"name": "Multiplayer Host", "path": "d/dosbox.exe", "arguments": "-conf server.conf"},
        ],
        converted=True,
    )
    assert callable(import_module(GogBackend().downloader_module).make_downloader)  # seam resolves
    layout.metadata_json.write_text(
        GameMetadataFile(
            scheme="gog",
            identifier="sample_dos_game",
            classification="dosbox",
            downloaded_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            launch_profiles=[
                LaunchProfile(slug=None, name="Play", is_default=True),
                LaunchProfile(slug="multiplayer_host", name="Multiplayer Host"),
            ],
        ).model_dump_json()
    )

    game = GogBackend().local_game("sample_dos_game")

    assert game.target == "gog:sample_dos_game"
    assert game.classification == "dosbox"
    assert game.converted is True
    assert [(m.slug, m.name, m.is_default) for m in game.launch_profiles] == [
        (None, "Play", True),
        ("multiplayer_host", "Multiplayer Host", False),
    ]


def test_gog_local_game_re_derives_profiles_when_metadata_has_none(downloads, base_profile_conf):
    """A migrated v1 file has an empty launch_profiles list - fall back to
    parsing the extracted goggame-*.info."""
    layout = _gog_download(
        downloads,
        "sample_dos_game",
        base_profile_conf,
        info_tasks=[
            {
                "name": "Play",
                "isPrimary": True,
                "path": "d/dosbox.exe",
                "arguments": "-conf primary.conf",
            },
        ],
    )
    layout.metadata_json.write_text(
        GameMetadataFile(scheme="gog", identifier="sample_dos_game").model_dump_json()
    )

    game = GogBackend().local_game("sample_dos_game")

    assert [m.name for m in game.launch_profiles] == ["Play"]
    assert game.launch_profiles[0].is_default is True


def test_gog_local_game_without_metadata_is_a_thin_entry(downloads):
    (downloads / "gog" / "bare_game").mkdir(parents=True)

    game = GogBackend().local_game("bare_game")

    assert game.identifier == "bare_game"
    assert game.classification is None
    assert game.converted is False
    assert [m.name for m in game.launch_profiles] == ["default"]


def test_iter_local_games_covers_every_download(downloads, base_profile_conf):
    _gog_download(downloads, "game_a", base_profile_conf)
    _gog_download(downloads, "game_b", base_profile_conf)

    names = {g.identifier for g in GogBackend().iter_local_games()}

    assert names == {"game_a", "game_b"}


# --- archive.org -------------------------------------------------------


def test_archive_local_game_from_a_v1_metadata_file(downloads):
    layout_dir = downloads / "archive" / "msdos_Sample_Game_1991"
    (layout_dir / "game").mkdir(parents=True)
    (layout_dir / "metadata.json").write_text(
        (Path(__file__).parent / "fixtures" / "metadata" / "archive_v1.json").read_text()
    )

    game = ArchiveBackend().local_game("msdos_Sample_Game_1991")

    assert game.title == "Sample Game (1991)"
    assert game.year == "1991"
    assert game.classification == "dosbox"
    assert [m.name for m in game.launch_profiles] == ["default"]
    assert game.converted is False
