"""Parse a GOG game's goggame-*.info file (shipped inside every extracted
install) into structured profile data - see GogProfile.
"""

import json
import shlex
from pathlib import Path

from .models import GogProfile


def find_game_info(extracted_dir: Path) -> Path | None:
    matches = list(extracted_dir.rglob("goggame-*.info"))
    return matches[0] if matches else None


def _split_windows_args(arguments: str) -> list[str]:
    """Split a GOG playTask arguments string into tokens, unquoting any
    "..." segments. Non-POSIX shlex so the Windows-style backslash paths
    inside survive (POSIX shlex would treat "\\" as an escape)."""
    lexer = shlex.shlex(arguments, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = ""  # '#' is an ordinary character in a path/arg
    return [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in lexer]


def _conf_basenames(arguments: str) -> list[str]:
    tokens = _split_windows_args(arguments)
    confs = []
    prev = None
    for tok in tokens:
        if prev == "-conf":
            confs.append(tok.replace("\\", "/").rsplit("/", 1)[-1])
        prev = tok
    return confs


def parse_profiles(extracted_dir: Path) -> list[GogProfile]:
    """Return every file-launchable playTask recorded in the game's
    goggame-*.info, or an empty list if there isn't one (older/manually
    packaged titles)."""
    info_path = find_game_info(extracted_dir)
    if info_path is None:
        return []

    data = json.loads(info_path.read_text())
    profiles = []
    for task in data.get("playTasks", []):
        path = task.get("path")
        if not path:
            continue
        arguments = task.get("arguments", "")
        profiles.append(
            GogProfile(
                name=task.get("name", ""),
                category=task.get("category"),
                is_primary=bool(task.get("isPrimary")),
                path=path,
                arguments=arguments,
                working_dir=task.get("workingDir", ""),
                conf_files=_conf_basenames(arguments),
            )
        )
    return profiles
