"""Tests for the `dedb ls` command.

`ls` scans <download_dir>/<backend>/ for one dir per game. `get_download_dir`
is imported into dedb.dedb.cli, so tests patch it there (not dedb.core).
"""

import pytest
from click.testing import CliRunner

from dedb.cli import cli
from dedb.dedb import cli as ls_module


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    root = tmp_path / "downloads"
    for path in ("gog/alpha_game", "gog/beta_game", "archive/msdos_Zzt"):
        (root / path).mkdir(parents=True)
    monkeypatch.setattr(ls_module, "get_download_dir", lambda backend: root / backend)
    return root


def test_ls_default_is_flat_sorted_and_bare(downloads):
    result = CliRunner().invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["alpha_game", "beta_game", "msdos_Zzt"]


def test_ls_default_qualifies_only_a_name_owned_by_two_backends(downloads):
    (downloads / "archive" / "alpha_game").mkdir()  # now under gog *and* archive

    result = CliRunner().invoke(cli, ["ls"])

    assert result.output.splitlines() == [
        "gog:alpha_game",  # collision -> one qualified line per backend
        "archive:alpha_game",
        "beta_game",  # unique -> bare
        "msdos_Zzt",
    ]


def test_ls_dash_one_is_bare_names_deduplicated(downloads):
    (downloads / "archive" / "alpha_game").mkdir()  # collision

    result = CliRunner().invoke(cli, ["ls", "-1"])

    assert result.output.splitlines() == ["alpha_game", "beta_game", "msdos_Zzt"]


def test_ls_long_qualifies_every_entry(downloads):
    (downloads / "archive" / "alpha_game").mkdir()  # collision

    result = CliRunner().invoke(cli, ["ls", "-l"])

    assert result.output.splitlines() == [
        "gog:alpha_game",
        "archive:alpha_game",
        "gog:beta_game",
        "archive:msdos_Zzt",
    ]


def test_ls_filtered_to_one_backend(downloads):
    result = CliRunner().invoke(cli, ["ls", "--type=gog"])

    assert result.output.splitlines() == ["alpha_game", "beta_game"]


def test_ls_unknown_backend_errors(downloads):
    result = CliRunner().invoke(cli, ["ls", "--type=bogus"])

    assert result.exit_code == 2
    assert "unknown backend 'bogus'" in result.output


def test_ls_rejects_conflicting_modes(downloads):
    result = CliRunner().invoke(cli, ["ls", "-1", "-l"])

    assert result.exit_code == 2
    assert "at most one" in result.output
