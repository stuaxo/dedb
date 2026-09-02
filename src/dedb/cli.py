"""Entry point for the dedb CLI.

Every command is contributed by an "app" (`Settings.apps`) - `dedb.dedb`
for the cross-cutting ones, plus `dedb.dosbox` / `dedb.gog` / `dedb.archive`.
Commands are registered flat on the root group; --help groups them per
app, Django manage.py style.
"""

import click

from .core import get_apps


class AppGroupedGroup(click.Group):
    """A click Group that lists commands flat but groups --help output
    under an "[app]" heading per contributing app."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
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


for _commands in get_apps().values():
    for _command in _commands:
        cli.add_command(_command)


if __name__ == "__main__":
    cli()
