"""Shims for a game's autoexec, applied only to userhook.bat. Real DOSBox
(via -conf) is never touched.

Each shim takes one line and returns a replacement line, unchanged if it
doesn't recognise it. Single-line only for now - move to whole-autoexec
context if a shim needs it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

SinglelineShim = Callable[[str], str]


def _split_line(line: str) -> tuple[str, list[str]]:
    """Split into (leading '@' or '', quote-aware tokens). Not shlex:
    backslashes in DOS paths would be read as escapes."""
    prefix, rest = ("@", line[1:]) if line.startswith("@") else ("", line)
    tokens = re.findall(r'"[^"]*"|\S+', rest)
    tokens = [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in tokens]
    return prefix, tokens


def choice_shim(line: str) -> str:
    """Strip CHOICE's flags (/C, /N, /S, /T...), keeping the command and
    prompt message. The flags are known to break keyboard input in some
    environments."""
    prefix, tokens = _split_line(line)
    if not tokens or tokens[0].lower() != "choice":
        return line
    kept = [tokens[0]] + [token for token in tokens[1:] if not token.startswith("/")]
    return prefix + " ".join(kept)


def mount_lredir_shim(working_dir: Path) -> SinglelineShim:
    """Convert MOUNT to DOSEMU2's LREDIR, resolving the DOS-relative path
    against working_dir (see dedb.gog.profiles.get_working_dir).

    "MOUNT C ..." is commented out, not converted: --Fdrive_c already
    maps C: to the game directory, and re-redirecting the drive
    userhook.bat is currently reading from corrupts command.com's
    position in that file (dosemu2 src/doc/README/lredir), truncating the
    rest of the batch.

    Run unsupported_mount_option("overlay") first in the pipeline, so
    overlay mounts are already REM'd (first token "REM", not "mount") by
    the time this shim runs.
    """

    def shim(line: str) -> str:
        prefix, tokens = _split_line(line)
        if not tokens or tokens[0].lower() != "mount" or len(tokens) < 3:
            return line

        drive, dos_path = tokens[1], tokens[2]
        if drive.rstrip(":").upper() == "C":
            return f"REM {line}"

        host_path = (working_dir / dos_path.replace("\\", "/")).resolve()
        return f"{prefix}LREDIR -f {drive.rstrip(':').upper()}: {host_path}"

    return shim


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


def unsupported_command(command: str) -> SinglelineShim:
    """Build a shim that comments out any line invoking command."""

    def shim(line: str) -> str:
        rest = line[1:] if line.startswith("@") else line
        tokens = rest.split()
        if tokens and tokens[0].lower() == command.lower():
            return f"REM {line}"
        return line

    return shim


def unsupported_mount_option(option: str) -> SinglelineShim:
    """Build a shim that comments out MOUNT only when it uses option
    (e.g. "overlay" for "-t overlay"). Other MOUNT lines pass through."""

    def shim(line: str) -> str:
        _prefix, tokens = _split_line(line)
        if not tokens or tokens[0].lower() != "mount":
            return line
        if not any(token.lower() == option.lower() for token in tokens):
            return line
        return f"REM {line}"

    return shim


unsupported_imgmount = unsupported_command("imgmount")
unsupported_overlay_mount = unsupported_mount_option("overlay")


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


@dataclass(frozen=True)
class Workaround:
    """One autoexec fix: a `shim` that rewrites the lines it recognises,
    its `severity` (which of the lists below it lives in), and a `summary`
    of the DOSEMU2 limitation it exists for.

    The shim is also the detection - any line it changes is, by
    definition, a line that needed working around (see diagnose_autoexec).
    """

    name: str
    severity: Severity
    summary: str
    shim: SinglelineShim


@dataclass(frozen=True)
class AutoexecIssue:
    """One autoexec line a Workaround rewrote: which workaround (and how
    severe), and the `rewritten` line that ends up in userhook.bat."""

    workaround: str
    severity: Severity
    summary: str
    line: str
    rewritten: str


# --- Workarounds, grouped by severity ---------------------------------
#
# These lists are the source of truth for what the shim pipeline does.
# active_workarounds() assembles them (plus the working-dir-dependent
# MOUNT entry) into the flat, ordered pipeline the rest of the code uses.

# No DOSEMU2 equivalent - the shim just comments the command out.
UNSUPPORTED: list[Workaround] = [
    Workaround(
        "imgmount",
        Severity.UNSUPPORTED,
        "IMGMOUNT (disk-image mounts) has no runtime equivalent in DOSEMU2",
        unsupported_imgmount,
    ),
    Workaround(
        "overlay-mount",
        Severity.UNSUPPORTED,
        "overlay MOUNT (-t overlay) has no equivalent - DOSEMU2 has no overlay filesystem",
        unsupported_overlay_mount,
    ),
]

# Still runs after the shim, but with changed behaviour.
PARTIALLY_SUPPORTED: list[Workaround] = [
    Workaround(
        "choice",
        Severity.PARTIALLY_SUPPORTED,
        "CHOICE flags (/C, /N, /S, /T...) stripped - they break keyboard input under DOSEMU2",
        choice_shim,
    ),
]

# Translated cleanly to a DOSEMU2 equivalent. Nothing qualifies
# unconditionally yet: MOUNT is the closest, but its LREDIR translation
# depends on a correctly resolved working directory, so it's treated as
# PARTIALLY_SUPPORTED (see _mount_workaround).
SUPPORTED: list[Workaround] = []


def _mount_workaround(working_dir: Path | None) -> Workaround:
    """The MOUNT workaround, which can't be a static list entry because it
    depends on working_dir: with one, MOUNT becomes LREDIR (a C: mount is
    dropped - --Fdrive_c already maps C:); without one it's commented
    out. Neither is a transparent translation, so it's PARTIALLY_SUPPORTED
    either way."""
    if working_dir is not None:
        return Workaround(
            "mount",
            Severity.PARTIALLY_SUPPORTED,
            "MOUNT rewritten to LREDIR (a C: mount is dropped - --Fdrive_c already maps C:)",
            mount_lredir_shim(working_dir),
        )
    return Workaround(
        "mount",
        Severity.PARTIALLY_SUPPORTED,
        "MOUNT commented out - translating it to LREDIR needs a known working directory",
        unsupported_command("mount"),
    )


def active_workarounds(working_dir: Path | None = None) -> list[Workaround]:
    """Every autoexec workaround, flattened into the order the pipeline
    applies them: unsupported commands are commented out first, then the
    partial/supported translations run on what's left. Same order the
    `dosboxconf --issues` report groups by (most severe first). The single
    source of truth for both autoexec_shims() and diagnose_autoexec()."""
    partial = [*PARTIALLY_SUPPORTED, _mount_workaround(working_dir)]
    return [*UNSUPPORTED, *partial, *SUPPORTED]


def autoexec_shims(autoexec: list[str], working_dir: Path | None = None) -> list[str]:
    """Run every line through each active workaround shim. working_dir
    converts MOUNT to LREDIR; without it MOUNT lines are commented out."""
    shims = [workaround.shim for workaround in active_workarounds(working_dir)]

    result = []
    for line in autoexec:
        for shim in shims:
            line = shim(line)
        result.append(line)
    return result


def diagnose_autoexec(autoexec: list[str], working_dir: Path | None = None) -> list[AutoexecIssue]:
    """List the autoexec lines that won't run cleanly under DOSEMU2, by
    running the real workaround pipeline and recording every line a
    workaround changed. Reusing the shims themselves as the detector
    keeps the reported issues in lockstep with the fixes actually applied
    to userhook.bat - they can't drift apart."""
    workarounds = active_workarounds(working_dir)

    issues: list[AutoexecIssue] = []
    for original in autoexec:
        line = original
        for workaround in workarounds:
            rewritten = workaround.shim(line)
            if rewritten != line:
                issues.append(
                    AutoexecIssue(
                        workaround.name,
                        workaround.severity,
                        workaround.summary,
                        original,
                        rewritten,
                    )
                )
            line = rewritten
    return issues
