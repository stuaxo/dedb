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


def test_ls_groups_by_backend_sorted(downloads):
    result = CliRunner().invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert result.output.index("gog/") < result.output.index("archive/")  # registry order
    assert result.output.index("alpha_game") < result.output.index("beta_game")  # sorted


def test_ls_filtered_to_one_backend(downloads):
    result = CliRunner().invoke(cli, ["ls", "--type=gog"])

    assert result.exit_code == 0
    assert "gog/" in result.output
    assert "archive/" not in result.output and "msdos_Zzt" not in result.output


@pytest.mark.parametrize("type_args", [["--type=archive,gog"], ["--type=archive", "--type=gog"]])
def test_ls_targets_form(downloads, type_args):
    result = CliRunner().invoke(cli, ["ls", "-1", *type_args])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["archive:msdos_Zzt", "gog:alpha_game", "gog:beta_game"]


def test_ls_unknown_backend_errors(downloads):
    result = CliRunner().invoke(cli, ["ls", "--type=bogus"])

    assert result.exit_code == 2
    assert "unknown backend 'bogus'" in result.output


def test_ls_empty_backend_shows_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "get_download_dir", lambda backend: tmp_path / backend)
    result = CliRunner().invoke(cli, ["ls", "--type=gog"])

    assert result.exit_code == 0
    assert "(none)" in result.output
