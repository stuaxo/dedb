"""Tests for the committed man pages under man/.

The Debian package installs them (debian/python3-dedb.manpages); they are
click-man's output, one page per command (see dedb.manpage). These fail
if the committed files drift - regenerate with `python man/_generate.py`.
"""

from pathlib import Path

import pytest

from dedb import __version__
from dedb.cli import cli
from dedb.manpage import render_man_pages

MAN = Path(__file__).parent.parent / "man"

PAGES = render_man_pages(cli, __version__)


@pytest.mark.parametrize("name", sorted(PAGES))
def test_committed_manpage_is_current(name: str) -> None:
    assert (MAN / name).read_text() == PAGES[name], (
        f"man/{name} is stale - run `python man/_generate.py`"
    )


def test_committed_set_matches_the_commands() -> None:
    committed = {p.name for p in MAN.glob("*.1")}

    assert committed == set(PAGES)


def test_every_command_has_a_page() -> None:
    for name in cli.commands:
        assert f"dedb-{name}.1" in PAGES
