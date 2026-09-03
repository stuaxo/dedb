"""Tests for the DOSEMU2 launch path shared shape of both runners:
ensure_converted() regenerates the config on every launch (rather than
only when it is missing), so a config never lingers from an older dedb.
"""

import pytest

from dedb.archive import runner as archive_runner
from dedb.archive.layout import ArchiveLayout
from dedb.gog import runner as gog_runner
from dedb.gog.layout import GogLayout


def test_archive_ensure_converted_reconverts_even_when_already_converted(tmp_path, monkeypatch):
    layout = ArchiveLayout(tmp_path, "x")
    layout.dosemu.mkdir(parents=True)
    layout.dosemu_conf.write_text("stale\n")  # is_converted() -> True

    calls = []
    monkeypatch.setattr(
        archive_runner, "import_archive_game", lambda lyt, force=False: calls.append(force)
    )

    assert archive_runner.ensure_converted(layout) == layout.dosemu_conf
    assert calls == [True]


def test_gog_ensure_converted_reconverts_even_when_already_converted(tmp_path, monkeypatch):
    layout = GogLayout(tmp_path, "x")
    layout.dosemu.mkdir(parents=True)
    layout.dosemu_conf.write_text("stale\n")  # is_converted() -> True

    monkeypatch.setattr(gog_runner, "_profile_file_slug", lambda lyt, profile: None)
    calls = []
    monkeypatch.setattr(
        gog_runner,
        "import_gog_game",
        lambda lyt, *, profile=None, force=False: calls.append((profile, force)),
    )

    assert gog_runner.ensure_converted(layout) == layout.dosemu_conf
    assert calls == [(None, True)]


def test_cmdline_helpers_name_paths_without_reconverting(tmp_path, monkeypatch):
    """dosemu_conf_path / dosbox_conf_argv back --cmdline - they must not
    trigger a conversion (that's `ensure_converted`'s job, on a real run)."""
    from dedb.core import Target

    layout = ArchiveLayout(tmp_path, "x")
    target = Target("archive", "x", None, "archive://x")
    monkeypatch.setattr(
        archive_runner, "ensure_converted", lambda lyt: pytest.fail("must not reconvert")
    )
    monkeypatch.setattr(archive_runner, "load_metadata", lambda lyt: object())
    monkeypatch.setattr(archive_runner, "dosbox_argv", lambda meta: ["-c", "GAME.EXE"])

    assert archive_runner.dosemu_conf_path(layout, target) == layout.dosemu_conf
    assert archive_runner.dosbox_conf_argv(layout, target) == (["-c", "GAME.EXE"], layout.game)
