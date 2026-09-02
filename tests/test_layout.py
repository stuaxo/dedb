"""Tests for the layout classes - the shared `LayoutPaths` mix-in plus each
backend's source-specific extras.
"""

from pathlib import Path

import click
import pytest

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


# --- removal --------------------------------------------------------------


def test_rm_methods_delete_only_their_own_subtree(tmp_path):
    layout = GogLayout(tmp_path / "downloads" / "gog", "doom")
    for d in (layout.game, layout.installer, layout.dosemu, layout.dosemu_local):
        d.mkdir(parents=True)
        (d / "f").write_text("x")

    layout.rm_installer()
    assert not layout.installer.exists()
    assert layout.game.is_dir() and layout.dosemu.is_dir()

    layout.rm_game()
    layout.rm_dosemu()
    assert not layout.game.exists() and not layout.dosemu.exists()
    assert layout.dosemu_local.is_dir()  # untouched
    assert layout.dir.is_dir()

    layout.rm()
    assert not layout.dir.exists()


def test_rm_of_an_absent_target_is_a_no_op(tmp_path):
    GogLayout(tmp_path / "downloads" / "gog", "doom").rm_game()  # must not raise


@pytest.mark.parametrize("key", ["..", "../gog", "doom/sub", "", "."])
def test_safe_rmtree_refuses_an_item_that_is_not_a_direct_child(tmp_path, key):
    root = tmp_path / "downloads" / "gog"
    (root / "doom" / "sub").mkdir(parents=True)
    with pytest.raises(click.ClickException, match="Refusing"):
        GogLayout(root, key).rm()


def test_safe_rmtree_refuses_a_symlinked_item_pointing_outside(tmp_path):
    root = tmp_path / "downloads" / "gog"
    root.mkdir(parents=True)
    outside = tmp_path / "precious"
    outside.mkdir()
    (root / "link").symlink_to(outside)

    with pytest.raises(click.ClickException, match="Refusing"):
        GogLayout(root, "link").rm()
    assert outside.is_dir()


def test_safe_rmtree_refuses_a_shallow_download_root():
    with pytest.raises(click.ClickException, match="misconfigured"):
        GogLayout(Path("/gog"), "doom").rm_game()
