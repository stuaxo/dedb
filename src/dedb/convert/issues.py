"""Render ``diagnose_autoexec()``'s findings as the ``[issues]`` text
block shared by ``dedb dosboxconf --issues`` and ``dedb dosemuconf
--issues`` - what DOSEMU2 can't run from the autoexec as-is, and (with
``verbose``) each line's rewrite.
"""

from collections.abc import Sequence
from pathlib import Path

from .autoexec import AutoexecIssue, Severity, diagnose_autoexec

# Most severe first - the order the report groups its bands in.
SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.UNSUPPORTED,
    Severity.PARTIALLY_SUPPORTED,
    Severity.SUPPORTED,
)

# One-line gloss on each severity, shown after the heading in the
# verbose (`--issues -v`) report.
SEVERITY_BLURB: dict[Severity, str] = {
    Severity.SUPPORTED: "translated to a DOSEMU2 equivalent",
    Severity.PARTIALLY_SUPPORTED: "still runs, but not identically to DOSBox",
    Severity.UNSUPPORTED: "no DOSEMU2 equivalent - commented out; the game may misbehave",
}

# Heading for each severity's block in the default (compact) `--issues`
# report, phrased as the set of commands that band contains.
SEVERITY_HEADING: dict[Severity, str] = {
    Severity.SUPPORTED: "Commands translated to a DOSEMU2 equivalent:",
    Severity.PARTIALLY_SUPPORTED: "Commands only partially supported:",
    Severity.UNSUPPORTED: "Commands not supported as-is under DOSEMU2:",
}


def _format_issues(issues: Sequence[AutoexecIssue], *, verbose: bool = False) -> str:
    """Default: one block per severity band - a heading, then one
    triggered shim name per line (repr()'d, the way a set diff reads).
    verbose additionally lists every offending autoexec line and what it
    is rewritten to."""
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


def render_issues(
    autoexec: Sequence[str], working_dir: Path | None = None, *, verbose: bool = False
) -> str:
    """The ``[issues]`` block for a list of autoexec lines. ``working_dir``,
    if known, lets the report show MOUNT's LREDIR translation rather than
    reporting it as commented out."""
    return _format_issues(diagnose_autoexec(list(autoexec), working_dir), verbose=verbose)
