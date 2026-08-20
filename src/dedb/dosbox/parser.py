"""Parsing logic for dosbox.conf files."""

import configparser
from pathlib import Path
from typing import Sequence


def parse_dosbox_conf(path: Path) -> tuple[dict, list[str]]:
    """Parse a dosbox.conf file.

    Returns a tuple of (config_dict, autoexec_commands) where config_dict is
    a nested dict of all sections except [autoexec], and autoexec_commands
    is the ordered list of raw command lines from the [autoexec] section.
    """
    parser = configparser.ConfigParser(
        allow_no_value=True,
        strict=False,
        delimiters=("=",),
    )
    # Preserve case: DOS commands and option values are case sensitive,
    # and configparser lowercases option names by default.
    parser.optionxform = str
    parser.read(path)

    autoexec_commands: list[str] = []
    if parser.has_section("autoexec"):
        for key in parser.options("autoexec"):
            # raw=True: .items()/.get() run values through interpolation,
            # which turns a "no value" None into '' and loses the
            # distinction between "MOUNT C GAMES" and "SET PATH=".
            value = parser.get("autoexec", key, raw=True)
            if value is None:
                autoexec_commands.append(key)
            else:
                autoexec_commands.append(f"{key}={value}")

    config_dict: dict = {}
    for section in parser.sections():
        if section == "autoexec":
            continue
        config_dict[section] = dict(parser.items(section))

    return config_dict, autoexec_commands


def parse_dosbox_confs(paths: Sequence[Path]) -> tuple[dict, list[str]]:
    """Parse and merge multiple dosbox.conf files, the way DOSBox itself
    does when given several -conf arguments: options are merged section by
    section with later files overriding earlier ones on a per-key basis,
    and [autoexec] commands from every file are concatenated in order.
    """
    merged_config: dict = {}
    merged_autoexec: list[str] = []
    for path in paths:
        config, autoexec = parse_dosbox_conf(path)
        for section, options in config.items():
            merged_config.setdefault(section, {}).update(options)
        merged_autoexec.extend(autoexec)

    return merged_config, merged_autoexec
