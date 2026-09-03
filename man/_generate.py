"""Regenerate the committed man pages.

    python man/_generate.py

The pages are click-man's output (see dedb.manpage), one per command.
The Debian package installs them (debian/python3-dedb.manpages);
tests/test_manpage.py fails if the committed files drift.
"""

from pathlib import Path

from dedb import __version__
from dedb.cli import cli
from dedb.manpage import render_man_pages


def main() -> None:
    here = Path(__file__).parent
    for name in sorted(here.glob("*.1")):
        name.unlink()
    for name, text in render_man_pages(cli, __version__).items():
        (here / name).write_text(text)
        print(f"wrote man/{name}")


if __name__ == "__main__":
    main()
