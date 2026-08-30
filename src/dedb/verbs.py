"""Generic commands that name a game by URL: `dedb run|download|import|rm`.

Each resolves the GAME argument (see dedb.backends.resolve) to a backend
and dispatches. Registered onto the root group by dedb.cli.
"""

import sys
from pathlib import Path

import click

from .backends import resolve
from .core import get_backends


def _backend_option(func):
    """`-b/--backend <scheme>`: read GAME as a bare id for that backend
    rather than a <scheme>://<id> URL (the psql "components instead of a
    URI" form)."""
    return click.option(
        "--backend",
        "-b",
        default=None,
        metavar="SCHEME",
        help="Read GAME as a bare id for this backend, rather than a <scheme>://<id> URL.",
    )(func)


def _resolve_game(game: str, backend: "str | None", *, profile: "str | None" = None):
    """resolve(), honouring the -b/--backend option: `NAME -b gog` is the
    same as `gog://NAME`."""
    if backend is not None:
        registry = get_backends()
        if backend not in registry:
            raise click.UsageError(f"Unknown backend '{backend}'. Known: {', '.join(registry)}.")
        if "://" in game:
            raise click.UsageError("Give a <scheme>://<id> URL or --backend, not both.")
        game = f"{backend}://{game}"
    return resolve(game, profile=profile)


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


def _run(game, backend, *, emulator, extra_args, verbose, keep, refresh_metadata, redownload) -> None:
    """Download (if needed) and launch a resolved game; exit non-zero if the emulator does."""
    layout = backend.ensure_downloaded(
        game.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    exit_code = backend.run(game, layout, emulator=emulator, extra_args=extra_args, verbose=verbose)
    if exit_code != 0:
        sys.exit(exit_code)


def _do_import(game, backend, *, output_dir, force, refreshconf, dumpconf, dumpuserhook) -> None:
    """Convert a resolved game to DOSEMU2 config(s), or --dump* them to stdout."""
    if dumpconf or dumpuserhook:
        entries = backend.build(game)
        for i, (label, conf_text, userhook_lines) in enumerate(entries):
            if i:
                click.echo()
            if len(entries) > 1:
                click.echo(f"[{label}]")
            if dumpconf:
                click.echo(conf_text, nl=False)
            if dumpuserhook:
                click.echo("\n".join(userhook_lines))
        return

    if refreshconf:
        if not backend.is_downloaded(game.identifier):
            click.echo(f"Skipping '{game.identifier}' (not downloaded)")
            return
        force = True

    dest = backend.convert(game, output_dir=output_dir, profile=game.profile, force=force)
    click.echo(f"Imported '{game.identifier}' -> '{dest}'")


@click.command("run")
@click.argument("game")
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, default=False, help="Run in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, default=False, help="Run in DOSEMU2.")
@click.option(
    "--profile",
    default=None,
    help="Launch profile (gog:// only). Same as gog://<id>?profile=<slug>.",
)
@_backend_option
@_download_options
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Print the command line before launching."
)
def run(
    game, emulator_args, use_dosbox, use_dosemu, profile, backend, keep, refresh_metadata, redownload, verbose
):
    """Run a game in DOSBox or DOSEMU2.

    GAME is gog://<id>, archive://<id>, an archive.org URL, or a name you
    have downloaded. It is downloaded, and for --dosemu converted, first
    if needed. Arguments after `--` go straight to the emulator.
    """
    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    resolved = _resolve_game(game, backend, profile=profile)
    _run(
        resolved,
        get_backends()[resolved.scheme],
        emulator=emulator,
        extra_args=emulator_args,
        verbose=verbose,
        keep=keep,
        refresh_metadata=refresh_metadata,
        redownload=redownload,
    )


@click.command("download")
@click.argument("game")
@_backend_option
@_download_options
def download(game, backend, keep, refresh_metadata, redownload):
    """Download and extract a game.

    GAME needs a scheme (gog://<id>, archive://<id>, or an archive.org
    URL), or -b <scheme> with a bare id. A bare name works only for a
    game already downloaded.
    """
    resolved = _resolve_game(game, backend)
    get_backends()[resolved.scheme].ensure_downloaded(
        resolved.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    click.echo(f"Downloaded '{resolved.identifier}' ({resolved.scheme})")


@click.command("import")
@click.argument("game")
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write the DOSEMU2 config(s) into. Defaults to the download's dosemu/ dir.",
)
@click.option("--profile", default=None, help="Launch profile to convert (gog:// only).")
@_backend_option
@click.option("--force", "-f", is_flag=True, default=False, help="Overwrite an existing output dir.")
@click.option(
    "--refreshconf",
    is_flag=True,
    default=False,
    help="Regenerate the config for an already-downloaded game (implies --force; skips if not downloaded).",
)
@click.option("--dumpconf", is_flag=True, default=False, help="Print the dosemu.conf instead of writing.")
@click.option(
    "--dumpuserhook", is_flag=True, default=False, help="Print the userhook.bat instead of writing."
)
def import_target(game, output_dir, profile, backend, force, refreshconf, dumpconf, dumpuserhook):
    """Import an already-downloaded game into DOSEMU2 config(s)."""
    resolved = _resolve_game(game, backend, profile=profile)
    _do_import(
        resolved,
        get_backends()[resolved.scheme],
        output_dir=output_dir,
        force=force,
        refreshconf=refreshconf,
        dumpconf=dumpconf,
        dumpuserhook=dumpuserhook,
    )


@click.command("rm")
@click.argument("game")
@_backend_option
@click.option("--yes", "-y", is_flag=True, default=False, help="Remove without prompting.")
def rm(game, backend, yes):
    """Delete a downloaded game's whole directory tree."""
    resolved = _resolve_game(game, backend)
    get_backends()[resolved.scheme].remove(resolved.identifier, assume_yes=yes)


GENERIC_COMMANDS = [run, download, import_target, rm]
