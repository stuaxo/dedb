"""Render ``diagnose_autoexec()``'s findings as the ``[issues]`` text
block shared by ``dedb dosboxconf --issues`` and ``dedb dosemuconf
--issues`` - what DOSEMU2 can't run from the autoexec as-is, and (with
``verbose``) each line's rewrite.
"""

from collections.abc import Iterator, Sequence
from itertools import groupby
from operator import attrgetter
from pathlib import Path

from .autoexec import AutoexecIssue, diagnose_autoexec


def _format_issues(issues: Sequence[AutoexecIssue], *, verbose: bool = False) -> Iterator[str]:
    yield "[issues]"
    if not issues:
        yield "(none)"
        return

    issues_by_severity = sorted(issues, key=attrgetter("severity", "workaround"))
    for severity, band in groupby(issues_by_severity, key=attrgetter("severity")):
        label = severity.name.lower().replace("_", " ")

        if not verbose:
            yield f"Commands {label}:"
            for workaround, _ in groupby(band, key=attrgetter("workaround")):
                yield repr(workaround)
            continue

        yield f"{label} ({severity.__doc__}):"
        for workaround, items in groupby(band, key=attrgetter("workaround")):
            group = list(items)
            yield f"  {workaround}: {group[0].summary}"
            for issue in group:
                yield f"    {issue.line}  ->  {issue.rewritten}"


def render_issues(
    autoexec: Sequence[str], working_dir: Path | None = None, *, verbose: bool = False
) -> str:
    """The ``[issues]`` block for a list of autoexec lines. ``working_dir``,
    if known, lets the report show MOUNT's LREDIR translation rather than
    reporting it as commented out."""
    return "\n".join(
        _format_issues(diagnose_autoexec(list(autoexec), working_dir), verbose=verbose)
    )
