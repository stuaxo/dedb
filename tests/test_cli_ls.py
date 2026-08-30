"""Tests for the root `dedb ls` command.

`ls` scans <download_dir>/<backend>/ for one dir per game. `get_download_dir`
is imported into dedb.cli, so tests patch it there (not dedb.core).
"""

import pytest
from click.testing import CliRunner

from dedb import cli as cli_module
from dedb.cli import cli


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    root = tmp_path / "downloads"
    for path in ("gog/alpha_game", "gog/beta_game", "archive/msdos_Zzt"):
        (root / path).mkdir(parents=True)
    monkeypatch.setattr(cli_module, "get_download_dir", lambda backend: root / backend)
    return root


def test_ls_default_is_a_flat_sorted_bare_list(downloads):
    result = CliRunner().invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["alpha_game", "beta_game", "msdos_Zzt"]


def test_ls_qualifies_only_names_owned_by_more_than_one_backend(downloads):
    (downloads / "archive" / "alpha_game").mkdir()  # now under gog *and* archive

    result = CliRunner().invoke(cli, ["ls"])

    assert result.output.splitlines() == [
        "gog:alpha_game",  # ambiguous -> qualified, one line per backend
        "archive:alpha_game",
        "beta_game",  # gog only -> bare
        "msdos_Zzt",  # archive only -> bare
    ]


def test_ls_targets_always_qualifies(downloads):
    result = CliRunner().invoke(cli, ["ls", "-1"])

    assert result.output.splitlines() == ["gog:alpha_game", "gog:beta_game", "archive:msdos_Zzt"]


def test_ls_long_groups_by_backend(downloads):
    result = CliRunner().invoke(cli, ["ls", "-l"])

    assert result.exit_code == 0
    assert "gog/" in result.output and "archive/" in result.output
    assert result.output.index("gog/") < result.output.index("archive/")
    assert result.output.index("alpha_game") < result.output.index("beta_game")


def test_ls_long_shows_none_for_empty_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "get_download_dir", lambda backend: tmp_path / backend)
    result = CliRunner().invoke(cli, ["ls", "-l", "--type=gog"])

    assert result.exit_code == 0
    assert "(none)" in result.output


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
