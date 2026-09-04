"""Regenerate the committed shell completion scripts.

    python completions/_generate.py

zsh and fish are click's own output; bash is a colon-aware variant (see
dedb.completion). The Debian package installs all three (see
debian/dedb.install); `dedb completion <shell>` prints the same
thing at runtime. tests/test_completion.py fails if the committed files
drift from `dedb.completion.completion_script`.
"""

from pathlib import Path

from dedb.cli import cli
from dedb.completion import SHELLS, completion_script


def main() -> None:
    here = Path(__file__).parent
    for shell in SHELLS:
        (here / f"dedb.{shell}").write_text(completion_script(shell, cli))
        print(f"wrote completions/dedb.{shell}")


if __name__ == "__main__":
    main()
