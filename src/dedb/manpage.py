"""Man pages for the ``dedb`` command, generated from the click CLI.

The pages under ``man/`` are installed by the Debian package
(debian/python3-dedb.manpages). ``man/_generate.py`` rewrites them from
this module and ``tests/test_manpage.py`` fails if the committed files
drift.

click-man is a dev/test dependency, not a runtime one, so it is imported
inside :func:`render_man_pages`.
"""

# A fixed date keeps the generated .TH headers reproducible from one run
# to the next; the release version is the part worth carrying.
MAN_DATE = "2026-01-01"

# click-man truncates each command's one-line summary at 45 columns, well
# short of the 80 `dedb --help` uses (see DedbGroup.format_commands); match
# it so the two listings read the same.
SHORT_HELP_LIMIT = 80


def render_man_pages(cli, version: str) -> dict[str, str]:
    """Map ``<name>.1`` -> roff text for ``cli`` and every visible subcommand."""
    import click
    import click_man.core as core

    _short_help = core.get_short_help_str
    core.get_short_help_str = lambda command, limit=SHORT_HELP_LIMIT: _short_help(command, limit)
    try:
        pages: dict[str, str] = {}

        def walk(command, name: str, parent_ctx) -> None:
            ctx = click.Context(command, info_name=name, parent=parent_ctx)
            pages[ctx.command_path.replace(" ", "-") + ".1"] = core.generate_man_page(
                ctx, version=version, date=MAN_DATE
            )
            for sub_name, sub in getattr(command, "commands", {}).items():
                if not getattr(sub, "hidden", False):
                    walk(sub, sub_name, ctx)

        walk(cli, "dedb", None)
        return pages
    finally:
        core.get_short_help_str = _short_help
