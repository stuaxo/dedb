"""Generic, URL-driven commands: `dedb run|download|import|rm <target>`.

Each resolves a target (see dedb.backends.resolve) to a backend and
dispatches. Registered onto the root group by dedb.cli. The per-backend
commands (downloadgog, ...) still exist; rungog/runarchive are now
deprecating wrappers over _run() here.
"""

import sys
from pathlib import Path

import click

from .backends import resolve
from .core import get_backends


def _download_options(func):
    """The --keep / --refreshmetadata / --redownload trio shared by `run`
    and `download`."""
    func = click.option(
        "--keep", is_flag=True, default=False, help="Keep the installer/archive after extracting."
    )(func)
    func = click.option(
        "--refreshmetadata",
        "-r",
        "refresh_metadata",
        is_flag=True,
        default=False,
        help="Re-fetch cached backend metadata instead of using the cached copy.",
    )(func)
    func = click.option(
        "--redownload",
        is_flag=True,
        default=False,
        help="Re-download and re-extract even if already present.",
    )(func)
    return func


def _require_one_emulator(use_dosbox: bool, use_dosemu: bool) -> str:
    if use_dosbox == use_dosemu:
        raise click.UsageError("Specify exactly one of --dosbox or --dosemu.")
    return "dosbox" if use_dosbox else "dosemu"


def _run(target, backend, *, emulator, extra_args, verbose, keep, refresh_metadata, redownload) -> None:
    """Shared body of `dedb run` and the deprecated rungog/runarchive."""
    layout = backend.ensure_downloaded(
        target.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    exit_code = backend.run(
        target, layout, emulator=emulator, extra_args=extra_args, verbose=verbose
    )
    if exit_code != 0:
        sys.exit(exit_code)


@click.command("run")
@click.argument("target")
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, default=False, help="Run in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, default=False, help="Run in DOSEMU2.")
@click.option(
    "--profile",
    default=None,
    help="Launch profile (gog:// only). Equivalent to gog://<id>?profile=<slug>.",
)
@_download_options
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Print the command line before launching."
)
def run(target, emulator_args, use_dosbox, use_dosemu, profile, keep, refresh_metadata, redownload, verbose):
    """Run a target in DOSBox or DOSEMU2.

    TARGET is gog://<id>, archive://<id>, an archive.org item URL, or the
    bare name of something already downloaded. Downloads (and, for
    --dosemu, converts) it first if needed. Anything after `--` is passed
    straight through to the emulator.
    """
    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    resolved = resolve(target, profile=profile)
    backend = get_backends()[resolved.scheme]
    _run(
        resolved,
        backend,
        emulator=emulator,
        extra_args=emulator_args,
        verbose=verbose,
        keep=keep,
        refresh_metadata=refresh_metadata,
        redownload=redownload,
    )


@click.command("download")
@click.argument("target")
@_download_options
def download(target, keep, refresh_metadata, redownload):
    """Download and extract a target.

    TARGET must carry a scheme (gog://<id>, archive://<id>, or an
    archive.org item URL) - a bare name only resolves once something is
    already downloaded.
    """
    resolved = resolve(target)
    backend = get_backends()[resolved.scheme]
    backend.ensure_downloaded(
        resolved.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    click.echo(f"Downloaded '{resolved.identifier}' ({resolved.scheme})")


@click.command("import")
@click.argument("target")
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write the DOSEMU2 config(s) into. Defaults to the download's dosemu/ dir.",
)
@click.option("--profile", default=None, help="Launch profile to convert (gog:// only).")
@click.option("--force", "-f", is_flag=True, default=False, help="Overwrite an existing output dir.")
def import_target(target, output_dir, profile, force):
    """Import an already-downloaded target into DOSEMU2 config(s)."""
    resolved = resolve(target, profile=profile)
    backend = get_backends()[resolved.scheme]
    dest = backend.convert(
        resolved, output_dir=output_dir, profile=profile or resolved.profile, force=force
    )
    click.echo(f"Imported '{resolved.identifier}' -> '{dest}'")


@click.command("rm")
@click.argument("target")
@click.option("--yes", "-y", is_flag=True, default=False, help="Remove without prompting.")
def rm(target, yes):
    """Delete a downloaded target's whole directory tree."""
    resolved = resolve(target)
    backend = get_backends()[resolved.scheme]
    backend.remove(resolved.identifier, assume_yes=yes)


GENERIC_COMMANDS = [run, download, import_target, rm]
