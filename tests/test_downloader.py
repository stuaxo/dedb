"""Tests for dedb.core.downloader.Downloader - the download/extract
template gog and archive share. A fake subclass records the hook calls;
the real filesystem effects come from a real GogLayout under tmp_path.
"""

import pytest

from dedb.core.downloader import Downloader
from dedb.gog.layout import GogLayout


class FakeDownloader(Downloader):
    fetch_result = True

    def __init__(self):
        self.calls = []

    def _prepare(self, layout, *, refresh):
        self.calls.append(("prepare", refresh))
        return "CTX"

    def _fetch(self, layout, ctx):
        self.calls.append(("fetch", ctx))
        return self.fetch_result

    def _extract(self, layout, ctx):
        self.calls.append(("extract", ctx))
        (layout.game / "GAME.EXE").write_text("MZ")  # -> is_downloaded()

    def _post_extract(self, layout):
        self.calls.append("post_extract")

    def _write_metadata(self, layout, ctx, *, refresh):
        self.calls.append(("write_metadata", refresh))
        layout.metadata_json.write_text("{}")

    def _rm_staging(self, layout):
        self.calls.append("rm_staging")


@pytest.fixture
def layout(tmp_path):
    return GogLayout(tmp_path / "downloads" / "gog", "x")


def _mark_downloaded(layout, *, metadata=True):
    layout.game.mkdir(parents=True)
    (layout.game / "old.exe").write_text("x")
    if metadata:
        layout.metadata_json.write_text("{}")


def test_fresh_download_runs_the_whole_pipeline(layout):
    dl = FakeDownloader()
    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=False)

    assert dl.calls == [
        ("prepare", False),
        ("fetch", "CTX"),
        ("extract", "CTX"),
        "post_extract",
        ("write_metadata", False),
        "rm_staging",
    ]
    assert layout.is_downloaded()
    assert layout.metadata_json.is_file()


def test_keep_skips_the_staging_cleanup(layout):
    dl = FakeDownloader()
    dl.ensure(layout, keep=True, refresh_metadata=False, redownload=False)
    assert "rm_staging" not in dl.calls


def test_a_fetch_that_returns_false_aborts_before_extract(layout):
    dl = FakeDownloader()
    dl.fetch_result = False
    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=False)

    assert dl.calls == [("prepare", False), ("fetch", "CTX")]
    assert not layout.is_downloaded()


def test_already_downloaded_and_no_flags_runs_no_hooks(layout, capsys):
    _mark_downloaded(layout)
    dl = FakeDownloader()
    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=False)

    assert dl.calls == []
    assert "Skipping: x (already downloaded)" in capsys.readouterr().out


def test_refresh_metadata_rewrites_metadata_without_re_fetching(layout):
    _mark_downloaded(layout)
    dl = FakeDownloader()
    dl.ensure(layout, keep=False, refresh_metadata=True, redownload=False)

    assert dl.calls == [("prepare", True), ("write_metadata", True), "post_extract"]
    assert layout.metadata_json.is_file()


def test_missing_metadata_is_written_even_without_refresh(layout):
    _mark_downloaded(layout, metadata=False)  # game present, metadata.json absent
    dl = FakeDownloader()
    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=False)

    assert dl.calls == [("prepare", False), ("write_metadata", False), "post_extract"]


def test_redownload_clears_the_old_copy_then_re_runs_the_pipeline(layout):
    _mark_downloaded(layout)
    layout.dosemu.mkdir(parents=True)
    layout.dosemu_conf.write_text("stale")
    dl = FakeDownloader()

    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=True)

    assert dl.calls == [
        "rm_staging",  # from the cleanup block
        ("prepare", False),
        ("fetch", "CTX"),
        ("extract", "CTX"),
        "post_extract",
        ("write_metadata", False),
        "rm_staging",
    ]
    assert not layout.dosemu_conf.is_file()  # stale config cleared
    assert (layout.game / "GAME.EXE").is_file()
    assert not (layout.game / "old.exe").is_file()  # old game files gone
