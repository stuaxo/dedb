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
    "-1",
    "as_targets",
    is_flag=True,
    default=False,
    help="Print one `<scheme>:<id>` target per line - pasteable into `dedb run` etc.",
)
def list_downloads(backends: list[str], as_targets: bool) -> None:
    """List locally-downloaded games/items per backend, by name.

    Scans <download_dir>/<backend>/ (see Configuration in the README) and
    lists each downloaded game/item, sorted by name.
    """
    for i, backend in enumerate(backends):
        download_dir = get_download_dir(backend)
        entries = (
            sorted(p.name for p in download_dir.iterdir() if p.is_dir())
            if download_dir and download_dir.is_dir()
            else []
        )

        if as_targets:
            for name in entries:
                click.echo(f"{backend}:{name}")
            continue

        if i:
            click.echo()
        click.echo(f"{backend}/")
        for name in entries:
            click.echo(f"  {name}")
        if not entries:
            click.echo("  (none)")


ROOT_COMMANDS = [list_downloads, *GENERIC_COMMANDS]

for _command in ROOT_COMMANDS:
    cli.add_command(_command)

for _commands in get_apps().values():
    for _command in _commands:
        cli.add_command(_command)


if __name__ == "__main__":
    cli()
