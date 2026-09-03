"""Parse dosbox.conf file(s) into a ``(sections, autoexec)`` pair -
``sections`` a nested ``{section: {key: str}}`` dict (``[autoexec]``
excluded), ``autoexec`` the ordered raw command lines of ``[autoexec]``.
``DosboxConfig.from_sections`` turns the pair into the model.
"""

import configparser
from collections.abc import Sequence
from pathlib import Path


def parse_dosbox_conf(path: Path) -> tuple[dict, list[str]]:
    """Parse one dosbox.conf file. See the module docstring for the shape."""
    parser = configparser.ConfigParser(
        allow_no_value=True,  # bare `MOUNT C GAME` autoexec lines have no `=`
        strict=False,  # tolerate a repeated section or key
        delimiters=("=",),
        interpolation=None,  # values are verbatim - `cycles=max 80%` keeps its `%`
    )
    parser.optionxform = str  # keep case: DOS commands and values are case-sensitive
    # cp437: DOSBox writes confs in it, and autoexec sections sometimes
    # hold CP437 box-drawing characters (ASCII-art menus).
    parser.read(path, encoding="cp437")

    autoexec = (
        [key if value is None else f"{key}={value}" for key, value in parser.items("autoexec")]
        if parser.has_section("autoexec")
        else []
    )
    sections = {name: dict(parser.items(name)) for name in parser.sections() if name != "autoexec"}
    return sections, autoexec


def parse_dosbox_confs(paths: Sequence[Path]) -> tuple[dict, list[str]]:
    """Parse and merge several dosbox.conf files the way DOSBox does with
    multiple -conf arguments: sections merge per key with the later file
    winning, [autoexec] lines concatenate in file order."""
    sections: dict = {}
    autoexec: list[str] = []
    for path in paths:
        file_sections, file_autoexec = parse_dosbox_conf(path)
        for name, options in file_sections.items():
            sections.setdefault(name, {}).update(options)
        autoexec += file_autoexec
    return sections, autoexec
