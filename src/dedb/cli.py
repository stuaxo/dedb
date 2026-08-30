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
        "Which download backend(s) to list. Repeatable and/or "
        "comma-separated: --type=gog --type=archive, or --type=gog,archive. "
        f"Default: all ({', '.join(DOWNLOAD_BACKENDS)})."
    ),
)
@click.option(
    "-s",
    "--short",
    "short",
    is_flag=True,
    default=False,
    help="Flat list; add a `<scheme>:` prefix only for names owned by more than one backend. (default)",
)
@click.option(
    "-1",
    "as_targets",
    is_flag=True,
    default=False,
    help="Flat list of fully-qualified `<scheme>:<id>` targets - pasteable into `dedb run` etc.",
)
@click.option(
    "-l",
    "--long",
    "grouped",
    is_flag=True,
    default=False,
    help="Group by backend under `<scheme>/` headings.",
)
def list_downloads(backends: list[str], short: bool, as_targets: bool, grouped: bool) -> None:
    """List locally-downloaded games/items.

    Default (-s): one name per line, sorted; a name is shown bare unless
    the same name exists under more than one backend, in which case it is
    shown as `<scheme>:<id>` for each. -1 always qualifies; -l groups by
    backend with headings.
    """
    if sum([bool(short), as_targets, grouped]) > 1:
        raise click.UsageError("Choose at most one of -s / -1 / -l.")

    games = _downloaded_games(backends)

    if grouped:
        for i, backend in enumerate(backends):
            if i:
                click.echo()
            click.echo(f"{backend}/")
            names = sorted((n for n, owners in games.items() if backend in owners), key=str.lower)
            for name in names:
                click.echo(f"  {name}")
            if not names:
                click.echo("  (none)")
        return

    for name in sorted(games, key=str.lower):
        owners = games[name]
        qualify = as_targets or len(owners) > 1
        for backend in owners:
            click.echo(f"{backend}:{name}" if qualify else name)


ROOT_COMMANDS = [list_downloads, *GENERIC_COMMANDS]

for _command in ROOT_COMMANDS:
    cli.add_command(_command)

for _commands in get_apps().values():
    for _command in _commands:
        cli.add_command(_command)


if __name__ == "__main__":
    cli()
