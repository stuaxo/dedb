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
        layout.staging.mkdir(parents=True, exist_ok=True)
        (layout.staging / "pkg").write_text("x")
        return self.fetch_result

    def _extract(self, layout, ctx):
        self.calls.append(("extract", ctx))
        (layout.game / "GAME.EXE").write_text("MZ")  # -> is_downloaded()

    def _post_extract(self, layout):
        self.calls.append("post_extract")

    def _write_metadata(self, layout, ctx, *, refresh):
        self.calls.append(("write_metadata", refresh))
        layout.metadata_json.write_text("{}")


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
    ]
    assert layout.is_downloaded()
    assert layout.metadata_json.is_file()
    assert not layout.staging.exists()  # cleaned up


def test_keep_leaves_the_staging_dir(layout):
    dl = FakeDownloader()
    dl.ensure(layout, keep=True, refresh_metadata=False, redownload=False)
    assert layout.staging.is_dir()


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


def test_rewrite_metadata_redoes_only_the_metadata_step(layout):
    _mark_downloaded(layout)
    (layout.game / "GAME.EXE").write_text("MZ")
    dl = FakeDownloader()

    dl.rewrite_metadata(layout)

    assert dl.calls == [("prepare", True), ("write_metadata", True), "post_extract"]
    assert layout.metadata_json.is_file()
    assert (layout.game / "old.exe").is_file()  # game files untouched
    assert not layout.staging.exists()  # nothing fetched


def test_gog_prepare_on_refresh_reads_the_product_id_from_metadata_json(layout, monkeypatch):
    """A refresh of an already-downloaded GOG game takes its product_id
    from the recorded metadata.json instead of a GOG library lookup."""
    from dedb.core import GameMetadataFile
    from dedb.gog.downloader import GogDownloader

    layout.dir.mkdir(parents=True)
    layout.metadata_json.write_text(
        GameMetadataFile(
            scheme="gog", identifier="x", source={"product_id": "42"}
        ).model_dump_json()
    )
    monkeypatch.setattr(
        "dedb.gog.downloader.GOGClient",
        lambda: pytest.fail("must not hit the GOG library on a refresh"),
    )

    assert GogDownloader()._prepare(layout, refresh=True) == "42"


def test_redownload_clears_the_old_copy_then_re_runs_the_pipeline(layout):
    _mark_downloaded(layout)
    layout.dosemu.mkdir(parents=True)
    layout.dosemu_conf.write_text("stale")
    dl = FakeDownloader()

    dl.ensure(layout, keep=False, refresh_metadata=False, redownload=True)

    assert dl.calls == [
        ("prepare", False),
        ("fetch", "CTX"),
        ("extract", "CTX"),
        "post_extract",
        ("write_metadata", False),
    ]
    assert not layout.dosemu_conf.is_file()  # stale config cleared
    assert not layout.staging.exists()  # re-fetched, then cleaned up again
    assert (layout.game / "GAME.EXE").is_file()
    assert not (layout.game / "old.exe").is_file()  # old game files gone
