"""Tests for the `dedb lsarchive` CLI command.

Only the network call is stubbed: `internetarchive.search_items` is
replaced with one replaying real result docs captured into
tests/fixtures/archive/. Everything downstream - the favorites client,
the sort, the output formatting - runs for real. The autouse
_isolate_dedb_config fixture (conftest) points settings at a throwaway
config dir.
"""

import json
from pathlib import Path

import pytest
import requests
from click.testing import CliRunner

from dedb import core
from dedb.cli import cli
from dedb.core.settings import Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures" / "archive"


@pytest.fixture
def configured_user(monkeypatch):
    monkeypatch.setattr(
        "dedb.core.settings.get_settings",
        lambda: Settings(archive={"archive_user": "someuser"}),
    )


@pytest.fixture
def stub_search(monkeypatch):
    """Replace search_items() with one recording the query it's handed and
    replaying captured real favorites docs. Assign stub_search['result']
    to override (an iterable, or an exception to raise)."""
    state = {"result": None}
    docs = json.loads((FIXTURES / "search_favorites.json").read_text())

    def _fake(query, *, fields=None, sorts=None):
        state["query"] = query
        result = state["result"]
        if isinstance(result, Exception):
            raise result
        return iter(docs if result is None else result)

    monkeypatch.setattr("dedb.archive.client.search_items", _fake)
    return state


def test_lists_favorites_as_targets_with_a_title_column(configured_user, stub_search):
    result = CliRunner().invoke(cli, ["lsarchive"])

    assert result.exit_code == 0
    assert "collection:fav-someuser" in stub_search["query"]
    lines = result.output.splitlines()
    assert lines[0] == f"{'archive:msdos_100000_Pyramid_1988':<50} $100,000 Pyramid (1988)"
    assert len(lines) == 5  # one per captured doc


def test_names_only_drops_the_title_column(configured_user, stub_search):
    result = CliRunner().invoke(cli, ["lsarchive", "-1"])

    assert result.output.splitlines()[0] == "archive:msdos_100000_Pyramid_1988"
    assert all(ln.startswith("archive:") and " " not in ln for ln in result.output.splitlines())


def test_user_and_all_flags_reach_the_query(configured_user, stub_search):
    CliRunner().invoke(cli, ["lsarchive", "--user", "override", "--all"])

    assert "collection:fav-override" in stub_search["query"]
    assert "softwarelibrary_msdos" not in stub_search["query"]  # --all drops the DOS filter


@pytest.mark.parametrize(("answer", "saved"), [("y", "prompteduser"), ("n", None)])
def test_prompts_for_an_unconfigured_user_and_offers_to_save(stub_search, answer, saved):
    load_settings()  # write the packaged default so there's a file to edit
    core.get_settings.cache_clear()

    result = CliRunner().invoke(cli, ["lsarchive"], input=f"prompteduser\n{answer}\n")

    assert result.exit_code == 0
    assert "collection:fav-prompteduser" in stub_search["query"]
    assert load_settings().archive.archive_user == saved


@pytest.mark.parametrize(
    ("result", "match"),
    [
        (requests.exceptions.ConnectionError("no route to host"), "Could not reach archive.org"),
        ([], "No favorites found"),  # empty search -> favorite_items raises LookupError
    ],
)
def test_client_errors_become_exit_1_messages(configured_user, stub_search, result, match):
    stub_search["result"] = result

    outcome = CliRunner().invoke(cli, ["lsarchive"])

    assert outcome.exit_code == 1
    assert match in outcome.output
