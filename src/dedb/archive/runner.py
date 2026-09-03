"""Run an archive.org item in DOSBox or DOSEMU2, downloading/converting
first if needed. Mirrors `dedb.gog.runner` without launch profiles.
"""

from collections.abc import Sequence
from pathlib import Path

from ..core import Target, get_settings, launch, launch_dosemu
from .importer import dosbox_argv, import_archive_game, load_metadata
from .layout import ArchiveLayout


def ensure_converted(layout: ArchiveLayout) -> Path:
    """(Re)generate the DOSEMU2 config + userhook, returning the conf path.

    Run on every launch - cheap and deterministic - so the config never
    lingers from an older dedb.
    """
    import_archive_game(layout, force=True)
    return layout.dosemu_conf


def dosbox_conf_argv(layout: ArchiveLayout, target: Target) -> tuple[list[str], Path]:
    """The emularity `dosbox` command line (mount C:, cd, run) as ``-c``
    args - no binary - and the dir it runs in. archive.org items have no
    dosbox.conf and no launch profiles, so ``target`` is unused."""
    return dosbox_argv(load_metadata(layout)), layout.game


def dosemu_conf_path(layout: ArchiveLayout, target: Target) -> Path:
    """The dosemu.conf `run --dosemu` uses - the path only, not regenerated."""
    return layout.dosemu_conf


def run_dosbox(
    layout: ArchiveLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    binary = get_settings().dosbox.get_dosbox_binary()
    argv, cwd = dosbox_conf_argv(layout, target)
    return launch(
        [binary, *argv, *extra_args],
        cwd=cwd,
        missing_hint=f"'{binary}' not found on PATH - install it first",
        verbose=verbose,
    )


def run_dosemu(
    layout: ArchiveLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    return launch_dosemu(
        layout,
        dosemu_conf=ensure_converted(layout),
        userhook_src=layout.userhook,
        extra_args=extra_args,
        verbose=verbose,
    )
