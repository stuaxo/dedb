"""Build the DOSBox model from a `dosbox` command line instead of a
dosbox.conf.

archive.org / emularity stores a DOS item's launch parameters the way
they'd be passed to the `dosbox` binary: repeatable `-c` commands, `-conf`
files, a few flags, and a trailing program. This module turns that argv
into the *same* ``(nested_section_dict, autoexec_lines)`` pair
``dedb.convert.parser`` produces from a .conf, so it flows through the
existing ``DosboxConfig.model_validate`` -> ``dosbox_to_dosemu`` ->
``convert_autoexec`` pipeline unchanged.

Two kinds of thing arrive on a DOSBox command line:

* **config settings** - ``-c "config -set <section> <prop>=<value>"`` (the
  internal CONFIG command) or ``-set "<section> <prop>=<value>"``
  (dosbox-staging's native option). These land in the section dict.
* **DOS commands** - ``-c "mount c c:\\dosgames"``, ``-c "c:"``,
  ``-c "cd doom"``, ``-c "doom.exe"``. These pass straight through as
  autoexec lines, in order, verbatim.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .converter import build_from_parsed
from .models import DosboxConfig, DosemuConfig
from .parser import parse_dosbox_confs
from .tokens import split_command

# The options this module reads, each taking one value and repeatable.
# `-fullscreen` and `-noautoexec` (bare, non-repeating) are handled inline
# in _scan_argv. Everything else starting with "-" is a host-side DOSBox
# flag with no DOSEMU2 equivalent: recognised, skipped (with its value, if
# it takes one) and recorded on DosboxCommandLine.ignored.
_REPEATED_VALUE_OPTS = ("-conf", "-c", "-set")

# Host-side flags known to take a value, so the value is skipped too and
# not mistaken for the trailing program. Not exhaustive - an unknown
# value-taking flag would leave its value as a stray token.
_HOST_VALUE_OPTS = ("-machine", "-lang", "-socket", "-scaler", "-forcescaler", "-savedir")


@dataclass
class DosboxCommandLine:
    """Structured result of parsing a `dosbox` argv. ``config`` and
    ``autoexec`` are the pair the rest of the engine consumes; the
    other fields are for reporting (see the notebook / tests)."""

    config: dict = field(default_factory=dict)  # nested {section: {key: str}}
    autoexec: list[str] = field(default_factory=list)
    conf_files: list[Path] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)  # recognised but dropped
    unmodelled: list[tuple[str, str]] = field(default_factory=list)  # not in DosboxConfig


@dataclass
class _Argv:
    conf: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    sets: list[str] = field(default_factory=list)
    fullscreen: bool = False
    noautoexec: bool = False
    program: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def _scan_argv(argv: Sequence[str]) -> _Argv:
    """Split a `dosbox` argv into its parts. The first token that isn't an
    option (or an option's value) starts the program run - it and every
    token after it belong to the program, as DOSBox itself treats them."""
    out = _Argv()
    tokens = list(argv)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            out.program = tokens[index:]
            break
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if token in _REPEATED_VALUE_OPTS and following is not None:
            {"-conf": out.conf, "-c": out.commands, "-set": out.sets}[token].append(following)
            index += 2
        elif token == "-fullscreen":
            out.fullscreen = True
            index += 1
        elif token == "-noautoexec":
            out.noautoexec = True
            index += 1
        elif token in _HOST_VALUE_OPTS and following is not None:
            out.ignored += [token, following]
            index += 2
        else:
            out.ignored.append(token)
            index += 1
    return out


def _config_fragment(payload: str) -> list[str] | None:
    """The token list of a ``config -set ...`` / ``-set ...`` payload, or
    None if this ``-c`` payload is a plain DOS command (i.e. autoexec)."""
    tokens = split_command(payload)
    lowered = [token.lower() for token in tokens]
    if lowered[:2] == ["config", "-set"]:
        return tokens[2:]
    if lowered[:1] == ["-set"]:
        return tokens[1:]
    return None


def _fragment_to_item(tokens: list[str]) -> tuple[str, str, str] | None:
    """``['sdl', 'fullscreen=true']`` / ``['cpu', 'cycles', 'max']`` /
    ``['cpu', 'cycles', 'fixed', '3000']`` -> ``(section, key, value)``.

    DOSBox accepts both ``prop=value`` and space-separated ``prop value``;
    a multi-token value (``fixed 3000``) is kept whole."""
    if len(tokens) < 2:
        return None
    section = tokens[0]
    remainder = " ".join(tokens[1:])
    if "=" in remainder:
        key, value = remainder.split("=", 1)
    else:
        key, _, value = remainder.partition(" ")
    return section, key.strip(), value.strip()


def parse_dosbox_command_line(
    argv: Sequence[str], *, base_dir: Path | None = None
) -> DosboxCommandLine:
    """Parse a `dosbox` argv into a DosboxCommandLine. Relative ``-conf``
    paths resolve against ``base_dir`` (default: the current directory),
    the same way DOSBox resolves them against its working directory."""
    scanned = _scan_argv(argv)
    result = DosboxCommandLine(ignored=list(scanned.ignored))

    base_dir = base_dir or Path.cwd()
    conf_paths = [
        path if (path := Path(raw)).is_absolute() else base_dir / raw for raw in scanned.conf
    ]
    result.conf_files = conf_paths

    # 1. -conf files first: DOSBox merges several -conf args per key with
    #    the later file winning; parse_dosbox_confs already does that.
    base_autoexec: list[str] = []
    if conf_paths:
        result.config, base_autoexec = parse_dosbox_confs(conf_paths)

    # 2. argv config items layer on top, overriding per key.
    fragments: list[list[str]] = [split_command(item) for item in scanned.sets]
    argv_autoexec: list[str] = []
    for payload in scanned.commands:
        fragment = _config_fragment(payload)
        if fragment is not None:
            fragments.append(fragment)
        else:
            argv_autoexec.append(payload)
    if scanned.fullscreen:
        fragments.append(["sdl", "fullscreen=true"])

    modelled = DosboxConfig.config_keys_by_section()
    for tokens in fragments:
        item = _fragment_to_item(tokens)
        if item is None:
            continue
        section, key, value = item
        result.config.setdefault(section, {})[key] = value
        if key not in modelled.get(section, {}):
            result.unmodelled.append((section, key))

    # 3. autoexec: conf [autoexec], then argv -c commands, then the
    #    trailing program. -noautoexec drops only the conf [autoexec].
    autoexec = [] if scanned.noautoexec else list(base_autoexec)
    autoexec.extend(argv_autoexec)
    if scanned.program:
        autoexec.append(" ".join(scanned.program))
    result.autoexec = autoexec

    return result


def parse_dosbox_argv(
    argv: Sequence[str], *, base_dir: Path | None = None
) -> tuple[dict, list[str]]:
    """A `dosbox` argv as the ``(nested_section_dict, autoexec_lines)``
    pair - the same contract as ``dedb.convert.parser.parse_dosbox_conf``."""
    result = parse_dosbox_command_line(argv, base_dir=base_dir)
    return result.config, result.autoexec


def build_from_argv(
    argv: Sequence[str], working_dir: Path | None = None, *, base_dir: Path | None = None
) -> tuple[DosemuConfig, list[str]]:
    """The argv analogue of ``dedb.convert.converter.build``: a `dosbox`
    command line -> ``(DosemuConfig, userhook_lines)`` with shims applied,
    through the same models as a dosbox.conf."""
    return build_from_parsed(*parse_dosbox_argv(argv, base_dir=base_dir), working_dir)
