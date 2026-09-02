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
) -> int:
    """Run ``cmd`` (in ``cwd`` if given), echoing it first when ``verbose``
    and turning a missing executable into a clean ``click.ClickException``
    carrying ``missing_hint``. Returns the child's exit code."""
    if verbose:
        rendered = shlex.join(cmd)
        if cwd is not None:
            rendered = f"cd {shlex.quote(str(cwd))} && {rendered}"
        click.echo(f"$ {rendered}")

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
) -> int:
    """Stage ``userhook_src`` as the game's userhook.bat and launch DOSEMU2
    with C: mapped to the extracted game directory."""
    layout.dosemu_local.mkdir(parents=True, exist_ok=True)

    # DOSEMU2's boot chain (dosrc.d/4uhook.bat) auto-runs only
    # %USERDRV%:\userhook.bat, and --Fdrive_c maps C: to layout.game - so
    # the generated userhook has to be copied there before every launch
    # (the active GOG launch profile can change between runs).
    shutil.copyfile(userhook_src, layout.game / "userhook.bat")

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls (see
        # dedb.shims.autoexec.mount_lredir_shim) only ever target paths
        # under the game's own directory - permit exactly that, nothing
        # wider.
        "-I",
        f'$_lredir_paths = "{layout.game}"',
        *extra_args,
    ]
    return launch(
        cmd,
        missing_hint="'dosemu' not found on PATH - install the dosemu2 package first",
        verbose=verbose,
    )
