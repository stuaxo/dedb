"""Autoexec shims: rewrite the lines of a game's autoexec that DOSEMU2
can't run as-is, for ``userhook.bat``. Real DOSBox (launched via ``-conf``)
never sees them.

Declarative. ``SHIMS`` routes an autoexec line - by regex - to a handler
that returns ``(rewritten_line, severity, summary)``.
``check_autoexec_line`` is the single matcher; ``convert_autoexec``
rewrites a whole autoexec for ``userhook.bat`` and ``diagnose_autoexec``
reports what it changed and why (backing ``dedb dosboxconf --issues``).
The shim is also the detector - a line it rewrites is, by definition, one
that needed working around - so the report can't drift from the file.
"""

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any


class Severity(Enum):
    """How well DOSEMU2 copes with the DOS command a shim covers.

    ``SUPPORTED``           - translated to a working DOSEMU2 equivalent.
    ``PARTIALLY_SUPPORTED`` - still runs after the shim, but not
                              identically to real DOSBox.
    ``UNSUPPORTED``         - no equivalent; the shim only comments it out
                              so it doesn't error. The game may misbehave.
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially supported"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class AutoexecIssue:
    """One autoexec line a shim rewrote: which shim (and how severe), the
    DOSEMU2 limitation it exists for, and the line before/after."""

    workaround: str
    severity: Severity
    summary: str
    line: str
    rewritten: str


# A handler's return: the line as it should appear in userhook.bat, how
# well DOSEMU2 copes, and a one-line note on the limitation.
ShimResult = tuple[str, Severity, str]
# Callable[..., ShimResult], but the **kwargs shape defeats a precise hint.
Handler = Any


# --- Shims -------------------------------------------------------------
#
# Each takes the matched line plus the routing regex's named groups (and
# `conf` / `working_dir` as keywords), and returns a ShimResult. Extra
# keywords it doesn't use are swallowed by **_.


def shim_imgmount(line: str, **_: Any) -> ShimResult:
    return (
        f"REM {line}",
        Severity.UNSUPPORTED,
        "IMGMOUNT (disk-image mounts) has no runtime equivalent in DOSEMU2",
    )


def shim_overlay_mount(line: str, **_: Any) -> ShimResult:
    return (
        f"REM {line}",
        Severity.UNSUPPORTED,
        "overlay MOUNT (-t overlay) has no equivalent - DOSEMU2 has no overlay filesystem",
    )


def shim_mount(
    line: str,
    drive: str,
    dos_path: str,
    working_dir: Path | None = None,
    **_: Any,
) -> ShimResult:
    """``MOUNT`` -> DOSEMU2's ``LREDIR``, resolving the DOS-relative path
    against ``working_dir``.

    ``C:`` is dropped: ``--Fdrive_c`` already maps it as a fatfs disk, and
    ``LREDIR`` (an mfs redirection) can't overlay that. Without a
    ``working_dir`` the target can't be resolved to a host path, so the
    line is only commented out.
    """
    if drive.upper() == "C":
        return (
            f"REM {line}",
            Severity.UNSUPPORTED,
            "MOUNT C: dropped - --Fdrive_c already maps C: to the game directory",
        )
    if working_dir is None:
        return (
            f"REM {line}",
            Severity.UNSUPPORTED,
            "MOUNT commented out - translating it to LREDIR needs a known working directory",
        )

    prefix = "@" if line.startswith("@") else ""
    host_path = (working_dir / dos_path.strip('"').replace("\\", "/")).resolve()
    return (
        f"{prefix}LREDIR -f {drive.upper()}: {host_path}",
        Severity.PARTIALLY_SUPPORTED,
        "MOUNT rewritten to LREDIR (a C: mount is dropped - --Fdrive_c already maps C:)",
    )


# --- Routing table ---------------------------------------------------
#
# (pattern, handler, name), tried in order - first match wins. The
# overlay and imgmount patterns come before the plain-mount one so
# `MOUNT ... -t overlay` and `IMGMOUNT` never fall through to shim_mount.

SHIMS: list[tuple[str, Handler, str]] = [
    (r"^\s*@?imgmount\b", shim_imgmount, "imgmount"),
    (r"^\s*@?mount\b.*-t\s+overlay\b", shim_overlay_mount, "overlay-mount"),
    (r'^\s*@?mount\s+(?P<drive>[a-zA-Z]):?\s+(?P<dos_path>"[^"]*"|\S+)', shim_mount, "mount"),
]


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[re.Pattern[str], Handler, str]]:
    return [(re.compile(pattern, re.IGNORECASE), handler, name) for pattern, handler, name in SHIMS]


def check_autoexec_line(
    line: str, conf: Any | None = None, working_dir: Path | None = None
) -> tuple[str, tuple[str, Severity, str] | None]:
    """Match one autoexec line against ``SHIMS``.

    Returns ``(line_for_userhook, hit)`` where ``hit`` is
    ``(shim_name, severity, summary)`` when a shim recognised the line, or
    ``None`` when it did not (and the line is returned unchanged).
    """
    clean = line.strip()
    if not clean:
        return line, None

    for pattern, handler, name in _compiled():
        match = pattern.match(clean)
        if match is None:
            continue
        rewritten, severity, summary = handler(
            line=clean, conf=conf, working_dir=working_dir, **match.groupdict()
        )
        return rewritten, (name, severity, summary)

    return line, None


def convert_autoexec(
    autoexec: list[str], conf: Any | None = None, working_dir: Path | None = None
) -> list[str]:
    """Every autoexec line rewritten for ``userhook.bat`` - each line
    unchanged unless a shim recognised it. ``working_dir`` lets the MOUNT
    shim resolve relative paths into ``LREDIR`` calls; without it MOUNT
    lines are commented out."""
    return [check_autoexec_line(line, conf, working_dir)[0] for line in autoexec]


def diagnose_autoexec(autoexec: list[str], working_dir: Path | None = None) -> list[AutoexecIssue]:
    """The autoexec lines that won't run cleanly under DOSEMU2: the same
    shim pass ``convert_autoexec`` runs, recording every line it changed
    and why."""
    issues: list[AutoexecIssue] = []
    for line in autoexec:
        rewritten, hit = check_autoexec_line(line, working_dir=working_dir)
        if hit is not None:
            name, severity, summary = hit
            issues.append(AutoexecIssue(name, severity, summary, line, rewritten))
    return issues
