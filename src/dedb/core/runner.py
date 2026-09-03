"""Emulator-launch building blocks shared by every backend's runner.

`dedb.gog.runner` and `dedb.archive.runner` differ only in how they build
the DOSBox command line (a GOG game has -conf files and launch profiles;
an archive.org item has a synthetic -c autoexec). Staging userhook.bat
for DOSEMU2 and the actual subprocess/verbose/"not installed" handling
are the same for both, and live here. (Which DOSBox binary to run is
`dedb.core.settings.DosboxSettings.binary`.)

``dosemu_argv`` / ``render_cmdline`` also back the ``--cmdline`` flag of
``run`` / ``dosboxconf`` / ``dosemuconf`` (see ``BackendBase.cmdline``).

``launch`` reports a missing emulator by re-raising ``FileNotFoundError``
with an install hint; the CLI turns that into a one-line error.
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .layout import LayoutPaths


def render_cmdline(cmd: Sequence[str], cwd: Path | None = None) -> str:
    """An emulator argv as one shell-pasteable line, prefixed with
    ``cd <cwd> &&`` when it has to run from a particular directory."""
    rendered = shlex.join(cmd)
    if cwd is not None:
        rendered = f"cd {shlex.quote(str(cwd))} && {rendered}"
    return rendered


def dosemu_argv(
    layout: LayoutPaths, dosemu_conf: Path, *, extra_args: Sequence[str] = ()
) -> list[str]:
    """The ``dosemu`` argv `run --dosemu` launches (the userhook staging in
    ``launch_dosemu`` aside). C: is the game dir; ``userhook.bat`` is run
    from its own ``-K`` drive so the game dir is never written to."""
    return [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls (see
        # dedb.convert.autoexec.shim_mount) and the -K hook drive
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


def launch(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    missing_hint: str,
    verbose: bool = False,
) -> int:
    """Run ``cmd`` (in ``cwd`` if given), echoing it first when ``verbose``
    and re-raising a missing executable as ``FileNotFoundError`` carrying
    ``missing_hint``. Returns the child's exit code."""
    if verbose:
        print(f"$ {render_cmdline(cmd, cwd)}")

    try:
        return subprocess.run(cmd, cwd=cwd).returncode
    except FileNotFoundError:
        raise FileNotFoundError(missing_hint) from None


def launch_dosemu(
    layout: LayoutPaths,
    *,
    dosemu_conf: Path,
    userhook_src: Path,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    """Stage ``userhook_src`` into ``layout.userhook_dir`` and launch DOSEMU2
    with C: mapped to the extracted game directory."""
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

    return launch(
        dosemu_argv(layout, dosemu_conf, extra_args=extra_args),
        missing_hint="'dosemu' not found on PATH - install the dosemu2 package first",
        verbose=verbose,
    )
