"""Run an archive.org item in DOSBox or DOSEMU2, downloading (and, for
DOSEMU2, converting) it first if that hasn't happened yet. Mirrors
dedb.gog.runner, minus the launch-profile handling GOG needs - an
archive.org item only ever has one launch mode.
"""

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

import click

from ..core import get_settings
from ..gog.runner import resolve_dosbox_binary
from .downloader import download_and_extract
from .importer import autoexec_commands, import_archive_game, load_metadata
from .layout import GameLayout


def ensure_downloaded(identifier: str, download_dir: Path, *, keep: bool = False) -> GameLayout:
    """Download and extract identifier if it isn't already, returning its layout."""
    layout = GameLayout(download_dir, identifier)
    if not layout.is_downloaded():
        download_and_extract(identifier, download_dir, keep=keep)
    return layout


def ensure_converted(layout: GameLayout) -> Path:
    """Convert layout to a DOSEMU2 config if that hasn't already been
    done, returning the resulting conf path."""
    if not layout.is_converted():
        import_archive_game(layout, force=True)
    return layout.dosemu_conf


def run_dosbox(layout: GameLayout, extra_args: Sequence[str] = (), verbose: bool = False) -> int:
    metadata = load_metadata(layout)
    binary = resolve_dosbox_binary(get_settings().dosbox.dosbox)

    # No dosbox.conf exists for archive.org items - hand DOSBox the same
    # synthetic autoexec userhook.bat would otherwise run, as -c commands.
    cmd = [binary]
    for command in autoexec_commands(metadata.emulator_start):
        cmd += ["-c", command]
    cmd += extra_args

    if verbose:
        click.echo(f"$ cd {shlex.quote(str(layout.game))} && {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=layout.game)
    except FileNotFoundError:
        raise click.ClickException(f"'{binary}' not found on PATH - install it first")
    return result.returncode


def run_dosemu(layout: GameLayout, extra_args: Sequence[str] = (), verbose: bool = False) -> int:
    dosemu_conf = ensure_converted(layout)
    layout.dosemu_local.mkdir(parents=True, exist_ok=True)

    # DOSEMU2's boot chain (dosrc.d/4uhook.bat) auto-runs only
    # %USERDRV%:\userhook.bat. --Fdrive_c maps C: to layout.game, so that
    # means layout.game/userhook.bat, not anything under layout.dosemu.
    shutil.copyfile(layout.userhook, layout.game / "userhook.bat")

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls (see dedb.shims.autoexec.mount_lredir_shim)
        # only ever target paths under the item's own directory - permit
        # exactly that, nothing wider.
        "-I",
        f'$_lredir_paths = "{layout.game}"',
    ]
    cmd += extra_args

    if verbose:
        click.echo(f"$ {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        raise click.ClickException("'dosemu' not found on PATH - install the dosemu2 package first")
    return result.returncode
