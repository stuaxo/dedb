"""Locating the ``MOUNT`` commands in a DOSBox ``[autoexec]`` and resolving
each to a host path.

``dedb.gog.downloader`` uses this to pre-create the directories a game's
autoexec MOUNTs - GOG's InnoSetup script would make them, but
``innoextract`` can't run that script. It is separate from the autoexec
*shims* (``dedb.convert.autoexec``), which have their own MOUNT handling
for ``userhook.bat``.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# A plain ``MOUNT <drive> <path>`` line. Not ``IMGMOUNT`` (a different
# command) and not ``MOUNT -u X`` (an unmount - the slot after MOUNT is a
# flag, not a drive letter).
_MOUNT_RE = re.compile(
    r'^\s*@?mount\s+(?P<drive>[a-zA-Z]):?\s+(?P<path>"[^"]*"|\S+)', re.IGNORECASE
)


@dataclass(frozen=True)
class MountPoint:
    """One MOUNT command's target: the DOS drive letter, the path as it
    was written, and that path resolved against a working directory."""

    dos_drive: str  # upper-case letter, no colon
    dos_path: str  # as written in the command, unquoted
    host_path: Path


def parse_mount_command(line: str) -> tuple[str, str] | None:
    """``(drive, dos_path)`` for a plain ``MOUNT <drive> <path>`` line, or
    ``None`` for anything else (IMGMOUNT, an unmount, a bare MOUNT)."""
    match = _MOUNT_RE.match(line)
    if match is None:
        return None
    return match["drive"].upper(), match["path"].strip('"')


def resolve_mounts(autoexec: list[str], working_dir: Path) -> list[MountPoint]:
    """Every ``MOUNT`` command in ``autoexec`` as a :class:`MountPoint`,
    each DOS-relative path resolved against ``working_dir`` into an
    absolute host path. IMGMOUNT and unmounts are skipped - MOUNT is the
    only command that targets a directory rather than a file."""
    mounts: list[MountPoint] = []
    for line in autoexec:
        parsed = parse_mount_command(line)
        if parsed is None:
            continue
        drive, dos_path = parsed
        host_path = (working_dir / dos_path.replace("\\", "/")).resolve()
        mounts.append(MountPoint(drive, dos_path, host_path))
    return mounts
