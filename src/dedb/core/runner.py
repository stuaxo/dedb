"""Emulator-launch building blocks shared by every backend's runner.

`dedb.gog.runner` and `dedb.archive.runner` differ only in how they build
the DOSBox command line (a GOG game has -conf files and launch profiles;
an archive.org item has a synthetic -c autoexec). Staging userhook.bat
for DOSEMU2 and the actual subprocess/verbose/"not installed" handling
are the same for both, and live here. (Which DOSBox binary to run is
`dedb.core.settings.DosboxSettings.binary`.)
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from .layout import LayoutPaths


def launch(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    missing_hint: str,
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """Run ``cmd`` (in ``cwd`` if given), echoing it first when ``verbose``
    and turning a missing executable into a clean ``click.ClickException``
    carrying ``missing_hint``. Returns the child's exit code.

    ``dry_run`` prints the command (a bare, shell-pasteable line, no
    ``$`` prefix) and returns 0 without running anything."""
    if verbose or dry_run:
        rendered = shlex.join(cmd)
        if cwd is not None:
            rendered = f"cd {shlex.quote(str(cwd))} && {rendered}"
        click.echo(rendered if dry_run else f"$ {rendered}")

    if dry_run:
        return 0

    try:
        return subprocess.run(cmd, cwd=cwd).returncode
    except FileNotFoundError:
        raise click.ClickException(missing_hint) from None


def launch_dosemu(
    layout: LayoutPaths,
    *,
    dosemu_conf: Path,
    userhook_src: Path,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """Stage ``userhook_src`` into ``layout.userhook_dir`` and launch DOSEMU2
    with C: mapped to the extracted game directory. ``dry_run`` skips the
    staging and just prints the command (see ``launch``)."""
    if not dry_run:
        layout.dosemu_local.mkdir(parents=True, exist_ok=True)
        layout.userhook_dir.mkdir(parents=True, exist_ok=True)

        # DOSEMU2's boot chain (dosrc.d/4uhook.bat) only auto-runs
        # %USERDRV%:\userhook.bat, and %USERDRV% is pinned to the drive-C
        # letter - so rather than write into the game dir (C:), stage the
        # active profile's userhook under a fixed name in a dedb-owned dir,
        # mount that dir as its own drive with -K, and run it with -E.
        shutil.copyfile(userhook_src, layout.userhook_dir / "userhook.bat")

        # Drop the stray userhook.bat older dedb versions copied into the
        # game dir, so an upgrade leaves the game files clean.
        (layout.game / "userhook.bat").unlink(missing_ok=True)

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls (see
        # dedb.convert.autoexec.mount_lredir_shim) and the -K hook drive
        # only ever touch paths under this one game's tree - permit exactly
        # that, nothing wider.
        "-I",
        f'$_lredir_paths = "{layout.dir}"',
        "-K",
        str(layout.userhook_dir),
        "-E",
        "USERHOOK.BAT",
        *extra_args,
    ]
    return launch(
        cmd,
        missing_hint="'dosemu' not found on PATH - install the dosemu2 package first",
        verbose=verbose,
        dry_run=dry_run,
    )
