"""Click commands contributed by the dosbox app.

Commands are plain, flat click.Command objects (not a subgroup) — the
root CLI registers them directly so they run as `dedb importdosbox ...`,
not `dedb dosbox importdosbox ...`.
"""

from pathlib import Path

import click

from .converter import build as build_config
from .converter import convert as convert_config
from .inspector import inspect as inspect_conf

CONF_FILE = click.Path(exists=True, dir_okay=False, path_type=Path)


@click.command("importdosbox")
@click.argument("conf_files", nargs=-1, required=True, type=CONF_FILE)
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write dosemu.conf and userhook.bat into. Required unless --dumpconf/--dumpuserhook is given.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite OUTPUT_DIR if it already exists.",
)
@click.option(
    "--dumpconf",
    is_flag=True,
    default=False,
    help="Print the dosemu.conf it would create instead of writing any files.",
)
@click.option(
    "--dumpuserhook",
    is_flag=True,
    default=False,
    help="Print the userhook.bat it would create instead of writing any files.",
)
def importdosbox(
    conf_files: tuple[Path, ...],
    output_dir: Path | None,
    force: bool,
    dumpconf: bool,
    dumpuserhook: bool,
) -> None:
    """Import one or more dosbox.conf files into a DOSEMU2 config.

    Accepts multiple CONF_FILEs for a single game, merged in order (later
    files override earlier ones), just as DOSBox itself does with several
    -conf arguments. Produces dosemu.conf and userhook.bat in OUTPUT_DIR,
    or with --dumpconf/--dumpuserhook, prints them instead of writing.
    """
    if dumpconf or dumpuserhook:
        target, userhook_lines = build_config(list(conf_files))
        if dumpconf:
            click.echo(target.model_dump_dosemurc(), nl=False)
        if dumpuserhook:
            click.echo("\n".join(userhook_lines))
        return

    if output_dir is None:
        raise click.UsageError(
            "--output-dir is required unless --dumpconf/--dumpuserhook is given."
        )
    convert_config(list(conf_files), output_dir, force=force)
    sources = ", ".join(str(f) for f in conf_files)
    click.echo(f"Imported {sources} -> '{output_dir}'")


def _existing_conf(source: str) -> Path:
    path = Path(source)
    if not path.is_file():
        raise click.BadParameter(
            f"{source!r} is not an existing dosbox.conf. For a downloaded game, pass "
            f"'gog://<id>' (or a bare id with --backend)."
        )
    return path


@click.command("dosboxconf")
@click.argument("sources", nargs=-1, required=True)
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
    """Show aspects of dosbox.conf(s), merged in order.

    SOURCES is one or more dosbox.conf paths, or a single downloaded game
    ('gog://<id>', or a bare id with --backend) whose resolved conf(s) are
    shown. With none of -a/-s/-g given, those three aspects are shown;
    --issues is always opt-in.
    """
    if backend is not None or (len(sources) == 1 and "://" in sources[0]):
        if len(sources) != 1:
            raise click.UsageError("Pass a single game when using a scheme or --backend.")
        from ..core import get_backends
        from ..verbs import _resolve_game

        game = _resolve_game(sources[0], backend, profile=profile)
        conf_files, working_dir = get_backends()[game.scheme].dosbox_sources(game)
    else:
        conf_files = [_existing_conf(source) for source in sources]
        working_dir = None

    click.echo(
        inspect_conf(
            conf_files,
            autoexec=autoexec,
            sblaster=sblaster,
            gus=gus,
            issues=issues,
            verbose=verbose,
            working_dir=working_dir if issues else None,
        )
    )


commands = [importdosbox, dosboxconf]
