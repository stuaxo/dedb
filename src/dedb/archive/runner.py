"""Run an archive.org item in DOSBox or DOSEMU2, downloading/converting
first if needed. Mirrors `dedb.gog.runner` without launch profiles.
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from ..core import get_settings, resolve_dosbox_binary
from .importer import autoexec_commands, import_archive_game, load_metadata
from .layout import ArchiveLayout


def ensure_converted(layout: ArchiveLayout) -> Path:
    """(Re)generate the DOSEMU2 config + userhook, returning the conf path.

    Run on every launch - cheap and deterministic - so the config never
    lingers from an older dedb.
    """
    import_archive_game(layout, force=True)
    return layout.dosemu_conf


def run_dosbox(layout: ArchiveLayout, extra_args: Sequence[str] = (), verbose: bool = False) -> int:
    metadata = load_metadata(layout)
    binary = resolve_dosbox_binary(get_settings().dosbox.dosbox)

    # No dosbox.conf for archive.org items - pass the synthetic autoexec as -c.
    cmd = [binary]
    for command in autoexec_commands(metadata.emulator_start):
        cmd += ["-c", command]
    cmd += extra_args

    if verbose:
        click.echo(f"$ cd {shlex.quote(str(layout.game))} && {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=layout.game)
    except FileNotFoundError:
        raise click.ClickException(f"'{binary}' not found on PATH - install it first") from None
    return result.returncode


def run_dosemu(layout: ArchiveLayout, extra_args: Sequence[str] = (), verbose: bool = False) -> int:
    dosemu_conf = ensure_converted(layout)
    layout.dosemu_local.mkdir(parents=True, exist_ok=True)

    # DOSEMU2's boot chain auto-runs only %USERDRV%:\userhook.bat, and
    # --Fdrive_c maps C: to layout.game - so copy it there.
    shutil.copyfile(layout.userhook, layout.game / "userhook.bat")

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls only target the item's own dir - permit only that.
        "-I",
        f'$_lredir_paths = "{layout.game}"',
    ]
    cmd += extra_args

    if verbose:
        click.echo(f"$ {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        raise click.ClickException(
            "'dosemu' not found on PATH - install the dosemu2 package first"
        ) from None
    return result.returncode
