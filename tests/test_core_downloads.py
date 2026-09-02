"""Tests for dedb.core.downloads: remove_download and ensure_download_dir.

remove_download takes a layout; the removal safety checks it relies on
(`LayoutPaths._safe_rmtree`) are tested in test_layout. ensure_download_dir
reads settings.download_dir, so patch dedb.core.settings.get_settings; the
temp-dir gate patches tempfile.gettempdir.
"""

from pathlib import Path

import click
import pytest

from dedb.core import ensure_download_dir, remove_download
from dedb.core.settings import Settings
from dedb.gog.layout import GogLayout

# --- remove_download -------------------------------------------------------


@pytest.fixture
def gog_root(tmp_path: Path) -> Path:
    """A populated <download_dir>/gog to delete items from."""
    root = tmp_path / "downloads" / "gog"
    (root / "doom" / "sub").mkdir(parents=True)
    (root / "doom" / "game.exe").write_bytes(b"x")
    return root


def test_removes_a_single_item(gog_root: Path):
    remove_download(GogLayout(gog_root, "doom"), assume_yes=True)
    assert not (gog_root / "doom").exists()
    assert gog_root.is_dir()  # only the item goes, not the root


def test_missing_item_is_a_no_op(gog_root: Path, capsys):
    remove_download(GogLayout(gog_root, "quake"), assume_yes=True)
    assert "Nothing to remove" in capsys.readouterr().out


def test_missing_download_dir_is_a_no_op(tmp_path: Path, capsys):
    remove_download(GogLayout(tmp_path / "downloads" / "gog", "doom"), assume_yes=True)
    assert "Nothing to remove" in capsys.readouterr().out


def test_propagates_a_safety_refusal(gog_root: Path):
    with pytest.raises(click.ClickException, match="Refusing"):
        remove_download(GogLayout(gog_root, "doom/sub"), assume_yes=True)


def test_removes_a_stray_file_child(gog_root: Path):
    (gog_root / "notes.txt").write_text("x")
    remove_download(GogLayout(gog_root, "notes.txt"), assume_yes=True)
    assert not (gog_root / "notes.txt").exists()


# --- ensure_download_dir --------------------------------------------------


@pytest.fixture
def set_download_dir(monkeypatch):
    def _set(path: Path) -> None:
        monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=path))

    return _set


def test_creates_the_app_subdir_when_download_dir_exists(tmp_path: Path, set_download_dir):
    set_download_dir(tmp_path)
    got = ensure_download_dir("gog")
    assert got == tmp_path / "gog"
    assert got.is_dir()


def test_creates_a_missing_download_dir_under_tmp(tmp_path: Path, set_download_dir, monkeypatch):
    fake_tmp = tmp_path / "tmp"
    fake_tmp.mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(fake_tmp))
    set_download_dir(fake_tmp / "throwaway")  # missing, but under the temp dir

    got = ensure_download_dir("gog")
    assert got == fake_tmp / "throwaway" / "gog"
    assert got.is_dir()


def test_refuses_a_missing_download_dir_outside_tmp(tmp_path: Path, set_download_dir, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "nowhere"))
    set_download_dir(tmp_path / "missing")
    with pytest.raises(click.ClickException, match="does not exist"):
        ensure_download_dir("gog")
