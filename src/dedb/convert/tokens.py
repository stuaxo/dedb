"""Tokenising a DOS command string - shared by the command-line parser
(``dedb.convert.cmdline``) and GOG playTask argument parsing
(``dedb.gog.gameinfo``).
"""

import re


def split_command(text: str) -> list[str]:
    """Tokenise a DOS command string: whitespace-separated, except a
    ``"double-quoted run"`` is a single token (and is unquoted). Not
    shlex - a backslash in a DOS path must not be read as an escape.
    """
    tokens = re.findall(r'"[^"]*"|\S+', text)
    return [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in tokens]
