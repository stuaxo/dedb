"""Generic commands that name a game by URL: `dedb
run|download|import|rm|refreshmetadata`.

`run` takes one GAME; `download` / `import` / `rm` / `refreshmetadata`
take any number. Each GAME resolves to a backend (see dedb.core.resolve);
`rm` also accepts shell wildcards matched against downloaded names.
Contributed to the root group by dedb.dedb.cli.
"""

import fnmatch
import re
import sys
from pathlib import Path

import click

from ..core import get_backends, remove_downloads, resolve_game, short_target


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


def _run(
    game, backend, *, emulator, extra_args, verbose, keep, refresh_metadata, redownload
) -> None:
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

    # The profile travels on the resolved target (game.profile); convert()
    # reads it from there - don't pass it as a separate kwarg.
    dest = backend.convert(game, output_dir=output_dir, force=force)
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
    game,
    emulator_args,
    use_dosbox,
    use_dosemu,
    profile,
    backend,
    keep,
    refresh_metadata,
    redownload,
    verbose,
):
    """Run a game in DOSBox or DOSEMU2.

    GAME is gog://<id>, archive://<id>, an archive.org URL, or a name you
    have downloaded. It is downloaded, and for --dosemu converted, first
    if needed. Arguments after `--` go straight to the emulator.
    """
    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    resolved = resolve_game(game, backend, profile=profile)
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
@click.argument("games", nargs=-1, required=True)
@_backend_option
@_download_options
def download(games, backend, keep, refresh_metadata, redownload):
    """Download and extract one or more games.

    Each GAME needs a scheme (gog:<id>, archive:<id>, or an archive.org
    URL), or -b <scheme> with a bare id. A bare name works only for a
    game already downloaded.
    """
    registry = get_backends()
    resolved = [resolve_game(g, backend) for g in games]  # resolve all before fetching any
    for target in resolved:
        registry[target.scheme].ensure_downloaded(
            target.identifier,
            keep=keep,
            refresh_metadata=refresh_metadata,
            redownload=redownload,
        )
        click.echo(f"Downloaded '{target.identifier}' ({target.scheme})")


@click.command("import")
@click.argument("games", nargs=-1, required=True)
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
@click.option(
    "--force", "-f", is_flag=True, default=False, help="Overwrite an existing output dir."
)
@click.option(
    "--refreshconf",
    is_flag=True,
    default=False,
    help="Regenerate the config for an already-downloaded game (implies --force; skips if not downloaded).",
)
@click.option(
    "--dumpconf", is_flag=True, default=False, help="Print the dosemu.conf instead of writing."
)
@click.option(
    "--dumpuserhook", is_flag=True, default=False, help="Print the userhook.bat instead of writing."
)
def import_target(games, output_dir, profile, backend, force, refreshconf, dumpconf, dumpuserhook):
    """Create DOSEMU2 config(s) for one or more downloaded programs."""
    registry = get_backends()
    resolved = [resolve_game(g, backend, profile=profile) for g in games]
    if len(resolved) > 1:
        if output_dir is not None:
            raise click.UsageError("--output-dir takes a single GAME.")
        if dumpconf or dumpuserhook:
            raise click.UsageError("--dumpconf / --dumpuserhook take a single GAME.")
    for target in resolved:
        _do_import(
            target,
            registry[target.scheme],
            output_dir=output_dir,
            force=force,
            refreshconf=refreshconf,
            dumpconf=dumpconf,
            dumpuserhook=dumpuserhook,
        )


_GLOB_CHARS = re.compile(r"[*?\[]")


def _rm_glob_hits(pattern: str, backend: "str | None", registry) -> list:
    """(backend, name) pairs whose downloaded name matches a shell
    wildcard - forced to one backend with -b, scheme-qualified
    (``gog:foo*``), or matched across every backend."""
    prefix, sep, bare = pattern.partition(":")
    if backend is not None:
        candidates = {backend: pattern}
    elif sep and prefix in registry:
        candidates = {prefix: bare.lstrip("/")}
    else:
        candidates = {scheme: pattern for scheme in registry}

    hits = []
    for scheme, pat in candidates.items():
        for name in fnmatch.filter(registry[scheme].local_names(), pat):
            hits.append((registry[scheme], name))
    return hits


@click.command("rm")
@click.argument("games", nargs=-1, required=True)
@_backend_option
@click.option("--yes", "-y", is_flag=True, default=False, help="Remove without prompting.")
def rm(games, backend, yes):
    """Delete one or more downloaded games' directory trees.

    Each GAME is a <scheme>://<id> URL, a bare downloaded name, or a
    shell wildcard (*, ?, [...]) matched against downloaded names -
    optionally scheme-qualified, e.g. 'gog:tyrian*'. One confirmation
    covers the whole set (skip it with -y).
    """
    registry = get_backends()

    pairs: list = []
    for game in games:
        if _GLOB_CHARS.search(game):
            hits = _rm_glob_hits(game, backend, registry)
            if not hits:
                click.echo(f"No downloads match '{game}'")
            pairs += hits
        else:
            target = resolve_game(game, backend)
            pairs.append((registry[target.scheme], target.identifier))

    seen: set = set()
    layouts = []
    for be, identifier in pairs:
        if (be.scheme, identifier) not in seen:
            seen.add((be.scheme, identifier))
            layouts.append(be.layout(identifier))

    if layouts:
        remove_downloads(layouts, assume_yes=yes)


@click.command("refreshmetadata")
@click.argument("games", nargs=-1)
@_backend_option
def refreshmetadata(games, backend):
    """Re-fetch backend metadata for downloaded games and rewrite each
    metadata.json. Downloads nothing.

    With no GAME, refreshes every downloaded game. Each GAME is a
    <scheme>://<id> URL, an archive.org URL, or a bare downloaded name
    (or -b <scheme> with a bare id). A GAME that resolves but isn't
    downloaded is skipped; an unrecognised GAME is an error.
    """
    registry = get_backends()

    if games:
        wanted = []
        for game in games:
            resolved = resolve_game(game, backend)  # raises on an unknown ref
            be = registry[resolved.scheme]
            if be.is_downloaded(resolved.identifier):
                wanted.append((be, resolved.identifier))
            else:
                click.echo(
                    f"Skipping {short_target(be.scheme, resolved.identifier)}: not downloaded"
                )
    else:
        wanted = [
            (be, name)
            for be in registry.values()
            for name in be.local_names()
            if be.is_downloaded(name)
        ]

    by_scheme: dict = {}
    for be, identifier in wanted:
        by_scheme.setdefault(be.scheme, []).append(identifier)

    for scheme, identifiers in by_scheme.items():
        registry[scheme].refresh_metadata(identifiers)

    done = sum(len(ids) for ids in by_scheme.values())
    click.echo(f"Refreshed metadata for {done} game{'' if done == 1 else 's'}")


GENERIC_COMMANDS = [run, download, import_target, rm, refreshmetadata]
