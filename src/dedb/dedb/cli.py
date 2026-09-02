"""Commands contributed by the dedb app itself: `ls` (spans every download
backend), plus the generic `run` / `download` / `import` / `rm` from
`dedb.dedb.verbs`. `dedb.core.get_apps()` reads `commands`.
"""

import click

from ..core import get_backends, get_download_dir, short_target
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


def _downloaded_games(backends: list[str]) -> "dict[str, list[str]]":
    """`{game name: [backends that have it], ...}`, each backend list in the
    given order."""
    games: dict[str, list[str]] = {}
    for backend in backends:
        root = get_download_dir(backend)
        if root and root.is_dir():
            for path in root.iterdir():
                if path.is_dir():
                    games.setdefault(path.name, []).append(backend)
    return games


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
def list_downloads(backends: list[str], short: bool, names_only: bool, qualified: bool) -> None:
    """List downloaded games."""
    if sum([bool(short), names_only, qualified]) > 1:
        raise click.UsageError("Choose at most one of -s / -1 / -l.")

    games = _downloaded_games(backends)

    for name in sorted(games, key=str.lower):
        owners = games[name]
        if names_only:
            click.echo(name)
        else:
            for backend in owners:
                qualify = qualified or len(owners) > 1
                click.echo(short_target(backend, name) if qualify else name)


commands = [list_downloads, *GENERIC_COMMANDS]
