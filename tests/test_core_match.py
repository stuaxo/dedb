"""Tests for dedb.core.match: shell-wildcard matching of game references
against downloaded games.

`match_downloads` reads each backend's `local_names()`, which walks
<download_dir>/<scheme>/ - tests point `dedb.core.settings.get_settings`
at a Settings with a tmp download_dir.
"""

import pytest

from dedb.core.match import has_wildcard, match_downloads
from dedb.core.settings import Settings


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    for rel in ("gog/tyrian_2000", "gog/tyrian_2k", "gog/doom", "archive/tyrian_x"):
        (tmp_path / rel).mkdir(parents=True)
    monkeypatch.setattr("dedb.core.settings.get_settings", lambda: Settings(download_dir=tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("token", "expected"),
    [("tyrian*", True), ("doom?", True), ("game[12]", True), ("gog:doom", False), ("plain", False)],
)
def test_has_wildcard(token, expected):
    assert has_wildcard(token) is expected


def _targets(hits):
    return sorted((be.scheme, identifier) for be, identifier in hits)


def test_bare_pattern_matches_across_every_backend(downloads):
    assert _targets(match_downloads("tyrian*")) == [
        ("archive", "tyrian_x"),
        ("gog", "tyrian_2000"),
        ("gog", "tyrian_2k"),
    ]


def test_scheme_qualified_pattern_pins_the_backend(downloads):
    assert _targets(match_downloads("gog:tyrian*")) == [
        ("gog", "tyrian_2000"),
        ("gog", "tyrian_2k"),
    ]


def test_backend_argument_pins_the_backend(downloads):
    assert _targets(match_downloads("tyrian*", backend="gog")) == [
        ("gog", "tyrian_2000"),
        ("gog", "tyrian_2k"),
    ]


def test_literal_token_matches_one_exact_name(downloads):
    assert _targets(match_downloads("doom")) == [("gog", "doom")]


def test_no_match_is_an_empty_list(downloads):
    assert match_downloads("zzz*") == []
