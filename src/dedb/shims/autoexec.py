"""Shims for a game's autoexec, applied only to userhook.bat. Real DOSBox
(via -conf) is never touched.

Each shim takes one line and returns a replacement line, unchanged if it
doesn't recognise it. Single-line only for now - move to whole-autoexec
context if a shim needs it.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
        return f'{prefix}LREDIR -f {drive.rstrip(":").upper()}: {host_path}'

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

# imgmount is not active: it works under real DOSBox, only DOSEMU2
# conversion can't translate it, and nothing handles that yet.
SHIMS: list[SinglelineShim] = [choice_shim, unsupported_overlay_mount]


def autoexec_shims(autoexec: list[str], working_dir: Path | None = None) -> list[str]:
    """Run every line through each active shim. working_dir converts
    MOUNT to LREDIR; without it MOUNT lines are commented out."""
    shims = list(SHIMS)
    shims.append(mount_lredir_shim(working_dir) if working_dir is not None else unsupported_command("mount"))

    result = []
    for line in autoexec:
        for shim in shims:
            line = shim(line)
        result.append(line)
    return result
