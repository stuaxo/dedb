"""Shims for a game's autoexec, applied only to userhook.bat. Real DOSBox
(via -conf) is never touched.

Each shim takes one line and returns a replacement line, unchanged if it
doesn't recognise it. Single-line only for now - move to whole-autoexec
context if a shim needs it.
"""

import re
from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any


def split_command(text: str) -> list[str]:
    """Tokenise a DOS command string: whitespace-separated, except a
    ``"double-quoted run"`` is a single token (and is unquoted). Not
    shlex - a backslash in a DOS path must not be read as an escape.
    Shared with dedb.gog.gameinfo (parsing playTask arguments)."""
    tokens = re.findall(r'"[^"]*"|\S+', text)
    return [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in tokens]


def _split_line(line: str) -> tuple[str, list[str]]:
    """Split an autoexec line into (leading '@' or '', tokens) - see
    :func:`split_command`."""
    prefix, rest = ("@", line[1:]) if line.startswith("@") else ("", line)
    return prefix, split_command(rest)


class Severity(Enum):
    """How well DOSEMU2 copes with the DOS command a workaround covers.

    SUPPORTED       - translated to a working DOSEMU2 equivalent.
    PARTIALLY_SUPPORTED - still runs after the shim, but not identically
                      to real DOSBox.
    UNSUPPORTED     - no equivalent; the shim only comments it out so it
                      doesn't error at runtime. The game may misbehave.
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially supported"
    UNSUPPORTED = "unsupported"


SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.UNSUPPORTED,
    Severity.PARTIALLY_SUPPORTED,
    Severity.SUPPORTED,
)

SEVERITY_BLURB: dict[Severity, str] = {
    Severity.SUPPORTED: "translated to a DOSEMU2 equivalent",
    Severity.PARTIALLY_SUPPORTED: "still runs, but not identically to DOSBox",
    Severity.UNSUPPORTED: "no DOSEMU2 equivalent - commented out; the game may misbehave",
}

SEVERITY_HEADING: dict[Severity, str] = {
    Severity.SUPPORTED: "Commands translated to a DOSEMU2 equivalent:",
    Severity.PARTIALLY_SUPPORTED: "Commands only partially supported:",
    Severity.UNSUPPORTED: "Commands not supported as-is under DOSEMU2:",
}


@dataclass(frozen=True)
class AutoexecIssue:
    """One autoexec line a Workaround rewrote: which workaround (and how
    severe), and the `rewritten` line that ends up in userhook.bat."""

    workaround: str
    severity: Severity
    summary: str
    line: str
    rewritten: str


@dataclass(frozen=True)
class ResolvedMount:
    """One MOUNT command's target, resolved to a host path."""

    drive: str
    dos_path: str
    host_path: Path


def resolve_mounts(autoexec: list[str], working_dir: Path) -> list[ResolvedMount]:
    """Find every MOUNT command in autoexec, resolving each DOS-relative
    target against working_dir (see dedb.gog.profiles.get_working_dir)
    into an absolute host path. IMGMOUNT and other commands are ignored -
    MOUNT is the only one that targets a directory rather than a file."""
    resolved = []
    for line in autoexec:
        _prefix, tokens = _split_line(line)
        if len(tokens) < 3 or tokens[0].lower() != "mount" or tokens[1].startswith("-"):
            continue
        drive, dos_path = tokens[1], tokens[2]
        host_path = (working_dir / dos_path.replace("\\", "/")).resolve()
        resolved.append(ResolvedMount(drive.rstrip(":").upper(), dos_path, host_path))
    return resolved


# ==========================================
# 1. Shims (Return: rewritten_line, severity, summary)
# ==========================================


def shim_mount(
    line: str, drive: str, dos_path: str, working_dir: Path | None = None, **kwargs
) -> tuple[str, Severity, str]:
    if working_dir is None:
        return (
            f"REM {line}",
            Severity.PARTIALLY_SUPPORTED,
            "MOUNT commented out - translating it to LREDIR needs a known working directory",
        )
    if drive.upper().rstrip(":") == "C":
        return (
            f"REM {line}",
            Severity.PARTIALLY_SUPPORTED,
            "MOUNT rewritten to LREDIR (a C: mount is dropped - --Fdrive_c already maps C:)",
        )

    dos_path = dos_path.strip('"')
    prefix = "@" if line.startswith("@") else ""
    host_path = (working_dir / dos_path.replace("\\", "/")).resolve()

    return (
        f"{prefix}LREDIR -f {drive.upper().rstrip(':')}: {host_path}",
        Severity.PARTIALLY_SUPPORTED,
        "MOUNT rewritten to LREDIR (a C: mount is dropped - --Fdrive_c already maps C:)",
    )


def shim_imgmount(line: str, **kwargs) -> tuple[str, Severity, str]:
    return (
        f"REM {line}",
        Severity.UNSUPPORTED,
        "IMGMOUNT (disk-image mounts) has no runtime equivalent in DOSEMU2",
    )


def shim_unsupported_mount_option(line: str, **kwargs) -> tuple[str, Severity, str]:
    return (
        f"REM {line}",
        Severity.UNSUPPORTED,
        "overlay MOUNT (-t overlay) has no equivalent - DOSEMU2 has no overlay filesystem",
    )


def shim_choice(line: str, **kwargs) -> tuple[str, Severity, str]:
    prefix, tokens = _split_line(line)
    kept = [tokens[0]] + [token for token in tokens[1:] if not token.startswith("/")]
    rewritten = prefix + " ".join(kept)
    return (
        rewritten,
        Severity.PARTIALLY_SUPPORTED,
        "CHOICE flags (/C, /N, /S, /T...) stripped - they break keyboard input under DOSEMU2",
    )


SHIMS = [
    (r"^\s*@?imgmount\b.*$", shim_imgmount, "imgmount"),
    (r"^\s*@?mount\b.*-t\s+overlay.*$", shim_unsupported_mount_option, "overlay-mount"),
    (r"^\s*@?mount\s+(?P<drive>[a-zA-Z]:?)\s+(?P<dos_path>\"[^\"]*\"|\S+).*$", shim_mount, "mount"),
    (r"^\s*@?choice\b.*$", shim_choice, "choice"),
]


@cache
def get_shims():
    return [(re.compile(p, re.IGNORECASE), h, n) for p, h, n in SHIMS]


def check_autoexec_line(
    line: str, conf: Any | None, working_dir: Path | None
) -> tuple[str, tuple[str, Severity, str] | None]:
    clean = line.strip()
    if not clean:
        return line, None

    for pattern, handler, name in get_shims():
        if match := pattern.match(clean):
            rewritten, severity, summary = handler(
                line=clean, conf=conf, working_dir=working_dir, **match.groupdict()
            )
            return rewritten, (name, severity, summary)

    return line, None


def convert_autoexec(
    dosbox_lines: list[str], conf: Any | None = None, working_dir: Path | None = None
) -> list[str]:
    return [check_autoexec_line(line, conf, working_dir)[0] for line in dosbox_lines]


def autoexec_shims(autoexec: list[str], working_dir: Path | None = None) -> list[str]:
    return convert_autoexec(autoexec, conf=None, working_dir=working_dir)


def diagnose_autoexec(autoexec: list[str], working_dir: Path | None = None) -> list[AutoexecIssue]:
    return [
        AutoexecIssue(*shim_data, line, rewritten)
        for line in autoexec
        for rewritten, shim_data in [check_autoexec_line(line, conf=None, working_dir=working_dir)]
        if shim_data and rewritten != line
    ]


@dataclass(frozen=True)
class Workaround:
    """For backwards compatibility with __init__.py exports."""

    name: str
    severity: Severity
    summary: str
    shim: Any


def active_workarounds(*args, **kwargs):
    # Stub for backwards compatibility with __init__.py exports.
    return []


# Stubs for backwards compatibility in tests and __init__.py


def choice_shim(line: str) -> str:
    rewritten, _s, _sum = shim_choice(line)
    return rewritten


def mount_lredir_shim(working_dir):
    def shim(line):
        _prefix, tokens = _split_line(line)
        if len(tokens) < 3 or tokens[0].lower() != "mount":
            return line
        rewritten, _s, _sum = shim_mount(
            line, drive=tokens[1], dos_path=tokens[2], working_dir=working_dir
        )
        return rewritten

    return shim


def unsupported_command(cmd):
    def shim(line):
        rest = line[1:] if line.startswith("@") else line
        tokens = rest.split()
        if tokens and tokens[0].lower() == cmd.lower():
            return f"REM {line}"
        return line

    return shim


def unsupported_mount_option(option):
    def shim(line):
        _prefix, tokens = _split_line(line)
        if not tokens or tokens[0].lower() != "mount":
            return line
        if not any(token.lower() == option.lower() for token in tokens):
            return line
        return f"REM {line}"

    return shim
