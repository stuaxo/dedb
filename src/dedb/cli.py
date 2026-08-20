"""Main entry point for the dedb CLI.

Commands are contributed by "apps" (listed in Settings.apps, e.g.
dedb.dosbox) and registered here flat on the root command group —
`dedb importdosbox`, not `dedb dosbox importdosbox` — but --help still
groups them by contributing app, the way a Django project's manage.py
groups per-app commands.
"""

import click

from .core import get_apps


class AppGroupedGroup(click.Group):
    """A click Group that lists its commands flat but formats --help output
    grouped under an "[app]" heading per contributing app."""

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
