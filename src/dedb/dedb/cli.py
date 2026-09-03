"""Commands contributed by the dedb app itself: `ls` (spans every download
backend), plus the generic `run` / `download` / `import` / `rm` /
`refreshmetadata` from `dedb.dedb.verbs`. `dedb.core.get_apps()` reads `commands`.
"""

import click

from ..core import LocalGame, get_backends, short_target
from .verbs import GENERIC_COMMANDS

# Registered backends, each with a namespaced <download_dir>/<scheme>/ tree.
DOWNLOAD_BACKENDS = tuple(get_backends())


def _parse_backends(
    ctx: click.Context, param: click.Parameter, value: tuple[str, ...]
) -> list[str]:
    """Resolve --type: repeatable and/or comma-separated (`--type=gog
    --type=archive` or `--type=gog,archive`), de-duplicated, order
    preserved. Defaults to every backend when not given."""
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
    "--type",
    "backends",
    metavar="BACKEND",
    multiple=True,
    callback=_parse_backends,
    help=(
        "Download backend(s) to list, repeatable or comma-separated. "
        f"Default: all ({', '.join(DOWNLOAD_BACKENDS)})."
    ),
)
@click.option(
    "-s",
    "--short",
    "short",
    is_flag=True,
    default=False,
    help="Bare name; `<scheme>:` prefix only when >1 backend owns the name. (default)",
)
@click.option(
    "-1",
    "names_only",
    is_flag=True,
    default=False,
    help="Bare names only, deduplicated.",
)
@click.option(
    "-l",
    "--long",
    "qualified",
    is_flag=True,
    default=False,
    help="Every entry as a full `<scheme>:<id>` target (pasteable into `dedb run`).",
)
@click.option(
    "-v",
    "--verbose",
    "verbose",
    is_flag=True,
    default=False,
    help="Columns: target, title, classification, converted?, launch profiles.",
)
def list_downloads(
    backends: list[str], short: bool, names_only: bool, qualified: bool, verbose: bool
) -> None:
    """List downloaded games."""
    if sum([bool(short), names_only, qualified, verbose]) > 1:
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
        for scheme in owners[name]:
            qualify = qualified or len(owners[name]) > 1
            click.echo(short_target(scheme, name) if qualify else name)


commands = [list_downloads, *GENERIC_COMMANDS]
