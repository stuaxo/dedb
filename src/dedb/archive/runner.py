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


def run_dosbox(
    layout: ArchiveLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    # archive.org items have no launch profiles - `target` is unused, kept
    # only for a signature the core dispatcher shares with the gog runner.
    metadata = load_metadata(layout)
    binary = get_settings().dosbox.get_dosbox_binary()

    # No dosbox.conf for archive.org items - pass emularity's synthetic
    # command line (mount C:, cd, run) as -c commands.
    cmd = [binary, *dosbox_argv(metadata), *extra_args]

    return launch(
        cmd,
        cwd=layout.game,
        missing_hint=f"'{binary}' not found on PATH - install it first",
        verbose=verbose,
        dry_run=dry_run,
    )


def run_dosemu(
    layout: ArchiveLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    # dry_run: don't regenerate the config, just name the path run would use.
    dosemu_conf = layout.dosemu_conf if dry_run else ensure_converted(layout)
    return launch_dosemu(
        layout,
        dosemu_conf=dosemu_conf,
        userhook_src=layout.userhook,
        extra_args=extra_args,
        verbose=verbose,
        dry_run=dry_run,
    )
