"""Aspect inspection of a DOSBox config, backing the dosboxconf command.

The config can come from dosbox.conf file(s) (``inspect``) or from a
`dosbox` command line (``inspect_command_line`` - archive.org items have
no dosbox.conf, just an emularity-style command line). Both parse to the
same ``(section_dict, autoexec_lines)`` pair, which ``_render`` turns into
text.
"""

from collections.abc import Sequence
from pathlib import Path

from ..convert import parse_dosbox_argv, parse_dosbox_confs, render_issues


def _format_section(title: str, options: dict) -> str:
    lines = [f"[{title}]"]
    lines.extend(f"{key}={value}" for key, value in options.items())
    return "\n".join(lines)


def _format_autoexec(commands: Sequence[str]) -> str:
    lines = ["[autoexec]"]
    lines.extend(commands)
    return "\n".join(lines)


def _render(
    config: dict,
    autoexec_commands: Sequence[str],
    *,
    autoexec: bool,
    sblaster: bool,
    gus: bool,
    issues: bool,
    verbose: bool,
    working_dir: Path | None,
) -> str:
    """Render the requested aspects of an already-parsed (section_dict,
    autoexec_lines) pair.

    If none of autoexec/sblaster/gus/issues is requested, autoexec,
    sblaster and gus are all shown (issues stays opt-in). verbose expands
    the issues block to every rewritten line. working_dir, if known, lets
    the issues report show MOUNT's LREDIR translation rather than
    reporting it as commented out.
    """
    if not (autoexec or sblaster or gus or issues):
        autoexec = sblaster = gus = True

    blocks = []
    if issues:
        blocks.append(render_issues(autoexec_commands, working_dir, verbose=verbose))
    if autoexec:
        blocks.append(_format_autoexec(autoexec_commands))
    if sblaster:
        blocks.append(_format_section("sblaster", config.get("sblaster", {})))
    if gus:
        blocks.append(_format_section("gus", config.get("gus", {})))

    return "\n\n".join(blocks)


def inspect(
    paths: Sequence[Path],
    *,
    autoexec: bool = False,
    sblaster: bool = False,
    gus: bool = False,
    issues: bool = False,
    verbose: bool = False,
    working_dir: Path | None = None,
) -> str:
    """Render the requested aspects of one or more merged dosbox.conf
    files. See ``_render`` for the flags."""
    return _render(
        *parse_dosbox_confs(paths),
        autoexec=autoexec,
        sblaster=sblaster,
        gus=gus,
        issues=issues,
        verbose=verbose,
        working_dir=working_dir,
    )


def inspect_command_line(
    argv: Sequence[str],
    *,
    working_dir: Path | None = None,
    autoexec: bool = False,
    sblaster: bool = False,
    gus: bool = False,
    issues: bool = False,
    verbose: bool = False,
) -> str:
    """Render the requested aspects of a `dosbox` command line (an
    emularity-style argv, or a GOG game's -conf files as an argv). See
    ``_render`` for the flags."""
    return _render(
        *parse_dosbox_argv(argv, base_dir=working_dir),
        autoexec=autoexec,
        sblaster=sblaster,
        gus=gus,
        issues=issues,
        verbose=verbose,
        working_dir=working_dir,
    )
