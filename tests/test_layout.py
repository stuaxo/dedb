"""Tests for the layout classes - the shared `LayoutPaths` mix-in plus each
backend's source-specific extras.
"""

from dedb.archive.layout import GameLayout as ArchiveLayout
from dedb.gog.layout import GameLayout as GogLayout


def test_shared_paths_hang_off_the_item_dir(tmp_path):
    for layout in (GogLayout(tmp_path, "doom"), ArchiveLayout(tmp_path, "msdos_doom")):
        assert layout.game == layout.dir / "game"
        assert layout.metadata_json == layout.dir / "metadata.json"
        assert layout.dosemu == layout.dir / "dosemu"
        assert layout.dosemu_conf == layout.dir / "dosemu" / "dosemu.conf"
        assert layout.dosemu_local == layout.dir / "dosemu_local"


def test_dir_is_keyed_by_each_source_s_own_id_field(tmp_path):
    assert GogLayout(tmp_path, "doom").dir == tmp_path / "doom"
    assert ArchiveLayout(tmp_path, "msdos_doom").dir == tmp_path / "msdos_doom"


def test_is_downloaded_needs_a_non_empty_game_dir(tmp_path):
    layout = ArchiveLayout(tmp_path, "x")
    assert not layout.is_downloaded()
    layout.game.mkdir(parents=True)
    assert not layout.is_downloaded()  # empty
    (layout.game / "GAME.EXE").write_text("MZ")
    assert layout.is_downloaded()


def test_gog_profile_suffixed_paths(tmp_path):
    layout = GogLayout(tmp_path, "doom")
    assert layout.installer == layout.dir / "installer"
    assert layout.dosemu_conf_for(None) == layout.dosemu_conf
    assert layout.dosemu_conf_for("mp") == layout.dosemu / "dosemu_mp.conf"
    assert layout.userhook_for("mp") == layout.dosemu / "userhook_mp.bat"

    assert not layout.is_converted("mp")
    layout.dosemu.mkdir(parents=True)
    layout.dosemu_conf_for("mp").write_text("x")
    assert layout.is_converted("mp")
    assert not layout.is_converted()  # the default pair still absent


def test_archive_single_launch_paths(tmp_path):
    layout = ArchiveLayout(tmp_path, "x")
    assert layout.download == layout.dir / "download"
    assert layout.userhook == layout.dosemu / "userhook.bat"
