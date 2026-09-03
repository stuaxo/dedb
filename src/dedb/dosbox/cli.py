"""The `dosboxconf` command - inspect the DOSBox side of a conversion.

A flat click.Command; the root CLI registers it so it runs as
`dedb dosboxconf ...`. The engine it reads through is `dedb.convert`.
"""

import click

from ..core import complete_source, existing_conf, get_backends, is_game_ref, resolve_game
from .inspector import inspect_command_line


@click.command("dosboxconf")
@click.argument("sources", nargs=-1, required=True, shell_complete=complete_source)
@click.option(
    "--backend",
    "-b",
    default=None,
    metavar="SCHEME",
    help="Read SOURCES as one bare game id for this backend, rather than dosbox.conf paths.",
)
@click.option("--profile", default=None, help="Launch profile, for a gog:// game.")
@click.option("--autoexec", "-a", is_flag=True, default=False, help="Show the [autoexec] commands.")
@click.option(
    "--sblaster",
    "-s",
    is_flag=True,
    default=False,
    help="Show Sound Blaster ([sblaster]) settings.",
)
@click.option(
    "--gus", "-g", is_flag=True, default=False, help="Show Gravis Ultrasound ([gus]) settings."
)
@click.option(
    "--issues",
    "-i",
    is_flag=True,
    default=False,
    help="List the commands DOSEMU2 can't run as-is, grouped by severity.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="With --issues, also show each autoexec line and what it is rewritten to.",
)
def dosboxconf(
    sources: tuple[str, ...],
    backend: str | None,
    profile: str | None,
    autoexec: bool,
    sblaster: bool,
    gus: bool,
    issues: bool,
    verbose: bool,
) -> None:
    """Show aspects of a DOSBox config, from dosbox.conf(s) or a game's
    launch command line.

    SOURCES is one or more dosbox.conf paths, or a single downloaded game
    ('gog:<id>' / 'archive:<id>', or a bare id with --backend) whose
    resolved DOSBox command line is shown - an archive.org item has no
    dosbox.conf, just the emularity command line. The game only needs to
    be downloaded, not imported. With none of -a/-s/-g given, those three
    aspects are shown; --issues is always opt-in.
    """
    if backend is not None or (len(sources) == 1 and is_game_ref(sources[0])):
        if len(sources) != 1:
            raise click.UsageError("Pass a single game when using a scheme or --backend.")
        game = resolve_game(sources[0], backend, profile=profile)
        argv, working_dir = get_backends()[game.scheme].dosbox_command_line(game)
    else:
        argv = [token for source in sources for token in ("-conf", str(existing_conf(source)))]
        working_dir = None

    click.echo(
        inspect_command_line(
            argv,
            working_dir=working_dir if issues else None,
            autoexec=autoexec,
            sblaster=sblaster,
            gus=gus,
            issues=issues,
            verbose=verbose,
        )
    )


commands = [dosboxconf]
