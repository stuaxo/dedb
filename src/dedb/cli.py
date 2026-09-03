"""The dedb CLI.

CLI is implemented with click, with commands in the root and then groups off
it.

The output is somewhat modelled on Djangos apps.
"""

import fnmatch
import re
import sys

import click

from . import completion as _completion
from .core import (
    LocalGame,
    complete_target,
    get_apps,
    get_backends,
    remove_downloads,
    render_cmdline,
    resolve_game,
    short_target,
)

# --- shared options / helpers ---------------------------------------------


def _backend_option(func):
    """`-b/--backend <scheme>`: Specify a backend e.g. archive/gog

    This is an alternative to using a <scheme>://<id>, allowing the use
    of raw game identifiers which may be useful for scripts.
    """
    return click.option(
        "--backend",
        "-b",
        default=None,
        metavar="SCHEME",
        help="Read GAME as a bare id for this backend, rather than a <scheme>://<id> URL.",
    )(func)


def _download_options(func):
    """The --keep / --refreshmetadata / --redownload trio shared by `run`
    and `download`.

    Allow files and metadata to be downloaded.
    """
    func = click.option(
        "--keep", is_flag=True, help="Keep the installer/archive after extracting."
    )(func)
    func = click.option(
        "--refreshmetadata",
        "-r",
        "refresh_metadata",
        is_flag=True,
        help="Re-fetch cached backend metadata instead of using the cached copy.",
    )(func)
    func = click.option(
        "--redownload",
        is_flag=True,
        help="Re-download and re-extract even if already present.",
    )(func)
    return func


def _complete_game(ctx, param, incomplete):
    """Shell completion for a GAME argument - `<scheme>:<id>` targets from
    local data, honouring a `-b <scheme>` already on the line."""
    return complete_target(incomplete, backend=ctx.params.get("backend"))


def _require_one_emulator(use_dosbox: bool, use_dosemu: bool) -> str:
    if use_dosbox == use_dosemu:
        raise click.UsageError("Specify exactly one of --dosbox or --dosemu.")
    return "dosbox" if use_dosbox else "dosemu"


# --- run / download ----------------------------------------------------


@click.command("run")
@click.argument("game", shell_complete=_complete_game)
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, help="Run in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, help="Run in DOSEMU2.")
@click.option(
    "--profile",
    default=None,
    help="Launch profile (gog:// only). Same as gog://<id>?profile=<slug>.",
)
@_backend_option
@_download_options
@click.option("--verbose", "-v", is_flag=True, help="Print the command line before launching.")
@click.option(
    "--cmdline",
    is_flag=True,
    help="Print the command --dosbox/--dosemu would run and stop "
    "(needs the game downloaded; writes nothing).",
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
    cmdline,
):
    """Run a game in DOSBox or DOSEMU2.

    GAME is specified as <scheme>:<identifier> or -b <scheme> <identifier>,
    or just <identifier> for downloaded games.

    An emulator must be specified with --dosbox or --dosemu.

    Arguments after `--` go straight to the emulator.

    --cmdline shows the emulator commandline instead of running it.
    """
    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    resolved = resolve_game(game, backend, profile=profile)
    be = get_backends()[resolved.scheme]
    if cmdline:
        cmd, cwd = be.cmdline(resolved, emulator=emulator, extra_args=emulator_args)
        click.echo(render_cmdline(cmd, cwd))
        return

    layout = be.ensure_downloaded(
        resolved.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    exit_code = be.run(
        resolved, layout, emulator=emulator, extra_args=emulator_args, verbose=verbose
    )
    if exit_code != 0:
        sys.exit(exit_code)


@click.command("download")
@click.argument("games", nargs=-1, required=True, shell_complete=_complete_game)
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


# --- rm ----------------------------------------------------------------


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
@click.argument("games", nargs=-1, required=True, shell_complete=_complete_game)
@_backend_option
@click.option("--yes", "-y", is_flag=True, help="Remove without prompting.")
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

    # A name can match several patterns; de-duplicate, keeping first-seen order.
    unique = {(be.scheme, identifier): be for be, identifier in pairs}
    layouts = [be.layout(identifier) for (_, identifier), be in unique.items()]

    if layouts:
        remove_downloads(layouts, assume_yes=yes)


# --- refreshmetadata --------------------------------------------------


@click.command("refreshmetadata")
@click.argument("games", nargs=-1, shell_complete=_complete_game)
@_backend_option
def refreshmetadata(games, backend):
    """Re-fetch backend metadata for games and rewriting each metadata.json.

    If no games are specified, defaults to all downloaded games.

    Games are specified with <scheme>:<id> or -b <scheme> <id>

    Games that have not been downloaded are skipped.
    Games that don't exist (can't be resolved) are an error.
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

    done = len(wanted)
    click.echo(f"Refreshed metadata for {done} game{'' if done == 1 else 's'}")


# --- ls --------------------------------------------------------------


# Registered backends, each with a namespaced <download_dir>/<scheme>/ tree.
DOWNLOAD_BACKENDS = tuple(get_backends())


def _parse_backends(
    ctx: click.Context, param: click.Parameter, value: tuple[str, ...]
) -> list[str]:
    """Resolve `ls -b`: repeatable and/or comma-separated (`-b gog -b
    archive` or `-b gog,archive`), de-duplicated, order preserved.
    Defaults to every backend when not given."""
    selected: list[str] = []
    for chunk in value:
        for part in chunk.split(","):
            part = part.strip()
            if not part:
                continue

            if part not in DOWNLOAD_BACKENDS:
                raise click.BadParameter(
                    f"unknown backend '{part}' (choose from {', '.join(DOWNLOAD_BACKENDS)})",
                    ctx,
                    param,
                )
            if part not in selected:
                selected.append(part)
    return selected or list(DOWNLOAD_BACKENDS)


def _local_games(backends: list[str]) -> "list[LocalGame]":
    """Every downloaded game under the given backends, in backend order
    then name order. `iter_local_games()` builds on the same `local_names()`
    view that `dedb run`'s bare-name resolution uses."""
    registry = get_backends()
    games: list[LocalGame] = []
    for scheme in backends:
        games.extend(
            sorted(registry[scheme].iter_local_games(), key=lambda g: g.identifier.lower())
        )
    return games


def _owners(games: "list[LocalGame]") -> "dict[str, list[str]]":
    """`{identifier: [schemes that have it], ...}` for name qualification."""
    owners: dict[str, list[str]] = {}
    for game in games:
        owners.setdefault(game.identifier, []).append(game.scheme)
    return owners


@click.command("ls")
@click.option(
    "--backend",
    "-b",
    "backends",
    metavar="SCHEME",
    multiple=True,
    callback=_parse_backends,
    help=(
        "Backend(s) to list, repeatable or comma-separated. "
        f"Default: all ({', '.join(DOWNLOAD_BACKENDS)})."
    ),
)
@click.option(
    "-s",
    "--short",
    "short",
    is_flag=True,
    help="Bare name; `<scheme>:` prefix only when >1 backend owns the name. (default)",
)
@click.option(
    "-1",
    "names_only",
    is_flag=True,
    help="Bare names only, deduplicated.",
)
@click.option(
    "-l",
    "--long",
    "qualified",
    is_flag=True,
    help="Every entry as a full `<scheme>:<id>` target (pasteable into `dedb run`).",
)
@click.option(
    "-v",
    "--verbose",
    "verbose",
    is_flag=True,
    help="Columns: target, title, classification, converted?, launch profiles.",
)
def list_downloads(
    backends: list[str], short: bool, names_only: bool, qualified: bool, verbose: bool
) -> None:
    """List downloaded games."""
    if sum([short, names_only, qualified, verbose]) > 1:
        raise click.UsageError("Choose at most one of -s / -1 / -l / -v.")

    games = _local_games(backends)
    owners = _owners(games)

    if verbose:
        for game in sorted(games, key=lambda g: (g.identifier.lower(), g.scheme)):
            n = len(game.launch_profiles)
            click.echo(
                f"{game.target:<48} {(game.title or ''):<28} "
                f"{(game.classification or '-'):<9} "
                f"{'converted' if game.converted else '-':<9} "
                f"{n} profile{'' if n == 1 else 's'}"
            )
        return

    for name in sorted(owners, key=str.lower):
        if names_only:
            click.echo(name)
            continue
        qualify = qualified or len(owners[name]) > 1
        for scheme in owners[name]:
            click.echo(short_target(scheme, name) if qualify else name)


# --- shell completion ---------------------------------------------


@click.command()
@click.argument("shell", type=click.Choice(_completion.SHELLS))
def completion(shell: str) -> None:
    """Print a shell completion script for dedb.

    The Debian package installs these already. For a pip install, write
    the script where your shell looks for it, e.g. bash:

        dedb completion bash | sudo tee /usr/share/bash-completion/completions/dedb

    or, without root, source it from your shell's rc file:

        dedb completion bash > ~/.dedb-complete.bash
        echo 'source ~/.dedb-complete.bash' >> ~/.bashrc
    """
    click.echo(_completion.completion_script(shell, cli))


# --- the root group ------------------------------------------------


# Cross-cutting commands, not tied to one backend. Listed before the
# per-app groups in --help.
CORE_COMMANDS = [list_downloads, run, download, rm, refreshmetadata, completion]


class AppGroupedGroup(click.Group):
    """Lists commands flat, but groups --help output: the cross-cutting
    commands first, then an "[app]" section per contributing source app."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        def rows(commands):
            return [
                (c.name, c.get_short_help_str(limit=formatter.width or 80))
                for c in commands
                if c.name is not None and not c.hidden
            ]

        if core := rows(CORE_COMMANDS):
            with formatter.section("Commands"):
                formatter.write_dl(core)
        for app_name, commands in get_apps().items():
            if app := rows(commands):
                with formatter.section(f"[{app_name}]"):
                    formatter.write_dl(app)


@click.group(cls=AppGroupedGroup)
def cli() -> None:
    """dedb: DOSEMU2 configuration tooling."""


for _command in CORE_COMMANDS:
    cli.add_command(_command)
for _commands in get_apps().values():
    for _command in _commands:
        cli.add_command(_command)


if __name__ == "__main__":
    cli()
