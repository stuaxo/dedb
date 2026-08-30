"""Main entry point for the dedb CLI.

Commands are contributed by "apps" (listed in Settings.apps, e.g.
dedb.dosbox) and registered here flat on the root command group —
`dedb importdosbox`, not `dedb dosbox importdosbox` — but --help still
groups them by contributing app, the way a Django project's manage.py
groups per-app commands.

A few cross-app commands (e.g. `ls`, which spans every download backend)
are defined here and shown under a "[dedb]" heading.
"""

import click

from .core import get_apps, get_backends, get_download_dir
from .verbs import GENERIC_COMMANDS

# Download backends `ls` knows about - each a registered backend with a
# namespaced <download_dir>/<scheme>/ tree of one dir per downloaded game/item.
# Sourced from the backend registry so there's a single source of truth.
DOWNLOAD_BACKENDS = tuple(get_backends())


class AppGroupedGroup(click.Group):
    """A click Group that lists its commands flat but formats --help output
    grouped under an "[app]" heading per contributing app (plus a "[dedb]"
    heading for commands defined on the root group itself)."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        app_command_names = {c.name for commands in get_apps().values() for c in commands}

        root_rows = []
        for name in self.list_commands(ctx):
            if name in app_command_names:
                continue
            command = self.get_command(ctx, name)
            if command is None or command.hidden:
                continue
            root_rows.append((name, command.get_short_help_str(limit=formatter.width or 80)))
        if root_rows:
            with formatter.section("[dedb]"):
                formatter.write_dl(root_rows)

        for app_name, commands in get_apps().items():
            rows = []
            for command in commands:
                if command.name is None or command.hidden:
                    continue
                help_text = command.get_short_help_str(limit=formatter.width or 80)
                rows.append((command.name, help_text))
            if rows:
                with formatter.section(f"[{app_name}]"):
                    formatter.write_dl(rows)


@click.group(cls=AppGroupedGroup)
def cli() -> None:
    """dedb: DOSEMU2 configuration tooling."""


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
    games: "dict[str, list[str]]" = {}
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
                click.echo(f"{backend}:{name}" if qualified or len(owners) > 1 else name)


ROOT_COMMANDS = [list_downloads, *GENERIC_COMMANDS]

for _command in ROOT_COMMANDS:
    cli.add_command(_command)

for _commands in get_apps().values():
    for _command in _commands:
        cli.add_command(_command)


if __name__ == "__main__":
    cli()
