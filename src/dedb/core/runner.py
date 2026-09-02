"""Emulator-launch building blocks shared by every backend's runner.

`dedb.gog.runner` and `dedb.archive.runner` differ only in how they build
the DOSBox command line (a GOG game has -conf files and launch profiles;
an archive.org item has a synthetic -c autoexec). Resolving the DOSBox
binary, staging userhook.bat for DOSEMU2 and the actual
subprocess/verbose/"not installed" handling are the same for both, and
live here.
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from .layout import LayoutPaths

# Logical [dosbox] dosbox= choice -> actual binary name on PATH. Only
# "dosbox" and "dosbox_staging" are tested; "dosbox_x" and "dosbox_pure"
# are included for people who want to try them.
DOSBOX_BINARIES = {
    "dosbox": "dosbox",
    "dosbox_staging": "dosbox-staging",
    "dosbox_x": "dosbox-x",
    "dosbox_pure": "dosbox-pure",
}

# "default" tries these, in order, and uses the first one installed.
_DEFAULT_PROBE_ORDER = ["dosbox_staging", "dosbox"]


def resolve_dosbox_binary(choice: str) -> str:
    """Map a [dosbox] dosbox= setting to the binary to actually run.
    "default" picks the first of dosbox_staging/dosbox found on PATH,
    falling back to plain "dosbox" if neither is, so the eventual
    FileNotFoundError still names the tool people know to install."""
    if choice == "default":
        for name in _DEFAULT_PROBE_ORDER:
            binary = DOSBOX_BINARIES[name]
            if shutil.which(binary):
                return binary
        return DOSBOX_BINARIES["dosbox"]

    if choice not in DOSBOX_BINARIES:
        valid = ", ".join(["default", *DOSBOX_BINARIES])
        raise click.ClickException(f'Unknown [dosbox] dosbox = "{choice}". Valid options: {valid}')
    return DOSBOX_BINARIES[choice]


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
