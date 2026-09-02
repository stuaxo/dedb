"""Aspect inspection of dosbox.conf files, backing the dosboxconf command."""

from collections.abc import Sequence
from pathlib import Path

from ..shims.autoexec import (
    SEVERITY_BLURB,
    SEVERITY_HEADING,
    SEVERITY_ORDER,
    AutoexecIssue,
    diagnose_autoexec,
)
from .parser import parse_dosbox_confs


def _format_section(title: str, options: dict) -> str:
    lines = [f"[{title}]"]
    lines.extend(f"{key}={value}" for key, value in options.items())
    return "\n".join(lines)


def _format_autoexec(commands: Sequence[str]) -> str:
    lines = ["[autoexec]"]
    lines.extend(commands)
    return "\n".join(lines)


def _format_issues(issues: Sequence[AutoexecIssue], *, verbose: bool = False) -> str:
    """Render diagnose_autoexec()'s findings.

    Default: one block per severity band - a heading, then one triggered
    workaround name per line (repr()'d, one per line, the way a set diff
    reads). verbose additionally lists every offending autoexec line and
    what it is rewritten to.
    """
    lines = ["[issues]"]
    if not issues:
        lines.append("(none)")
        return "\n".join(lines)

    for severity in SEVERITY_ORDER:
        in_band = [issue for issue in issues if issue.severity is severity]
        if not in_band:
            continue

        if not verbose:
            lines.append(SEVERITY_HEADING[severity])
            lines.extend(repr(name) for name in sorted({i.workaround for i in in_band}))
            continue

        lines.append(f"{severity.value} ({SEVERITY_BLURB[severity]}):")
        grouped: dict[str, tuple[str, list[AutoexecIssue]]] = {}
        for issue in in_band:
            grouped.setdefault(issue.workaround, (issue.summary, []))[1].append(issue)
        for name, (summary, group) in grouped.items():
            lines.append(f"  {name}: {summary}")
            for issue in group:
                lines.append(f"    {issue.line}  ->  {issue.rewritten}")
    return "\n".join(lines)


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
    """Render the requested aspects of one or more merged dosbox.conf files.

    If none of autoexec/sblaster/gus/issues is requested, autoexec,
    sblaster and gus are all shown (issues stays opt-in). verbose expands
    the issues block to every rewritten line. working_dir, if known, lets
    the issues report show MOUNT's LREDIR translation rather than
    reporting it as commented out.
    """
    if not (autoexec or sblaster or gus or issues):
        autoexec = sblaster = gus = True

    config, autoexec_commands = parse_dosbox_confs(paths)

    blocks = []
    if issues:
        blocks.append(
            _format_issues(diagnose_autoexec(autoexec_commands, working_dir), verbose=verbose)
        )
    if autoexec:
        blocks.append(_format_autoexec(autoexec_commands))
    if sblaster:
        blocks.append(_format_section("sblaster", config.get("sblaster", {})))
    if gus:
        blocks.append(_format_section("gus", config.get("gus", {})))

    return "\n\n".join(blocks)
