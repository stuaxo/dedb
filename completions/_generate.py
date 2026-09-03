"""Regenerate the committed shell completion scripts.

    python completions/_generate.py

Each file is click's own output (`click.shell_completion`) for the
`dedb` program - no local edits. The Debian package installs them (see
debian/python3-dedb.install); `dedb completion <shell>` prints the same
thing at runtime. tests/test_completion.py fails if the committed files
drift from what the installed click produces.
"""

from pathlib import Path

from click.shell_completion import get_completion_class

from dedb.cli import cli

SCRIPTS = {"bash": "dedb.bash", "zsh": "dedb.zsh", "fish": "dedb.fish"}


def script(shell: str) -> str:
    comp_cls = get_completion_class(shell)
    assert comp_cls is not None, shell
    return comp_cls(cli, {}, "dedb", "_DEDB_COMPLETE").source()


def main() -> None:
    here = Path(__file__).parent
    for shell, name in SCRIPTS.items():
        (here / name).write_text(script(shell))
        print(f"wrote completions/{name}")


if __name__ == "__main__":
    main()
