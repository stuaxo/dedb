"""Aspect inspection of dosbox.conf files, backing the dosboxconf command."""

from pathlib import Path
from typing import Sequence

from .parser import parse_dosbox_confs


def _format_section(title: str, options: dict) -> str:
    lines = [f"[{title}]"]
    lines.extend(f"{key}={value}" for key, value in options.items())
    return "\n".join(lines)


def _format_autoexec(commands: Sequence[str]) -> str:
    lines = ["[autoexec]"]
    lines.extend(commands)
    return "\n".join(lines)


def inspect(
    paths: Sequence[Path],
    *,
    autoexec: bool = False,
    sblaster: bool = False,
    gus: bool = False,
) -> str:
    """Render the requested aspects of one or more merged dosbox.conf files.

    If none of autoexec/sblaster/gus is requested, all three are shown.
    """
    if not (autoexec or sblaster or gus):
        autoexec = sblaster = gus = True

    config, autoexec_commands = parse_dosbox_confs(paths)

    blocks = []
    if autoexec:
        blocks.append(_format_autoexec(autoexec_commands))
    if sblaster:
        blocks.append(_format_section("sblaster", config.get("sblaster", {})))
    if gus:
        blocks.append(_format_section("gus", config.get("gus", {})))

    return "\n\n".join(blocks)
