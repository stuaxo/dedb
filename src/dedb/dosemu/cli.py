"""Click commands contributed by the dosemu app: `import` and `dosemuconf`.

Both take SOURCES that is either dosbox.conf paths or a downloaded game
reference, the same shape `dosboxconf` accepts. The conversion itself is
`dedb.convert`.
"""

from pathlib import Path

import click

from ..convert import build as build_config
from ..convert import convert as convert_config
from ..convert import parse_dosbox_argv, parse_dosbox_confs, render_issues
from ..core import (
    complete_source,
    existing_conf,
    get_backends,
    is_game_ref,
    render_cmdline,
    resolve_game,
)
from .inspector import render

_BACKEND_OPTION = click.option(
    "--backend",
    "-b",
    default=None,
    metavar="SCHEME",
    help="Read SOURCES as bare game ids for this backend, rather than dosbox.conf paths.",
)


def _do_import(game, backend, *, output_dir, force, refreshconf) -> None:
    """Convert a resolved game to DOSEMU2 config(s) on disk."""
    if refreshconf:
        if not backend.is_downloaded(game.identifier):
            click.echo(f"Skipping '{game.identifier}' (not downloaded)")
            return
        force = True

    # The profile travels on the resolved target (game.profile); convert()
    # reads it from there - don't pass it as a separate kwarg.
    dest = backend.convert(game, output_dir=output_dir, force=force)
    click.echo(f"Imported '{game.identifier}' -> '{dest}'")


def _conf_paths(sources: tuple[str, ...]) -> list[Path] | None:
    """The SOURCES as dosbox.conf paths if they all look like conf files
    (an existing file, or a ``.conf`` name), else None (they are game
    references)."""
    looks_conf = [s for s in sources if Path(s).suffix == ".conf" or Path(s).is_file()]
    if not looks_conf:
        return None
    if len(looks_conf) != len(sources):
        raise click.UsageError("SOURCES must be all dosbox.conf files or all game references.")
    return [existing_conf(s) for s in sources]


@click.command("import")
@click.argument("sources", nargs=-1, required=True, shell_complete=complete_source)
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write the DOSEMU2 config(s) into. "
    "For a game it defaults to the download's dosemu/ dir; for conf files it is required.",
)
@click.option("--profile", default=None, help="Launch profile to convert (gog only).")
@_BACKEND_OPTION
@click.option(
    "--force", "-f", is_flag=True, default=False, help="Overwrite an existing output dir."
)
@click.option(
    "--refreshconf",
    is_flag=True,
    default=False,
    help="Regenerate the config for an already-downloaded game (implies --force; skips if not downloaded).",
)
def import_target(sources, output_dir, profile, backend, force, refreshconf):
    """Create DOSEMU2 config(s) from downloaded games or dosbox.conf files.

    SOURCES is one or more downloaded games ('gog:<id>' / 'archive:<id>',
    an archive.org URL, a bare downloaded name, or bare ids with -b) -
    each converted into its own dosemu/ directory - OR one or more
    dosbox.conf paths merged (later files overriding earlier) into a
    single config written to --output-dir.
    """
    paths = None if backend is not None else _conf_paths(sources)

    if paths is not None:
        if output_dir is None:
            raise click.UsageError("--output-dir is required when importing dosbox.conf files.")
        if profile is not None or refreshconf:
            raise click.UsageError("--profile / --refreshconf apply to a game, not to conf files.")
        convert_config(paths, output_dir, force=force)
        click.echo(f"Imported {', '.join(str(p) for p in paths)} -> '{output_dir}'")
        return

    registry = get_backends()
    resolved = [resolve_game(s, backend, profile=profile) for s in sources]
    if len(resolved) > 1 and output_dir is not None:
        raise click.UsageError("--output-dir takes a single GAME.")
    for target in resolved:
        _do_import(
            target,
            registry[target.scheme],
            output_dir=output_dir,
            force=force,
            refreshconf=refreshconf,
        )


@click.command("dosemuconf")
@click.argument("sources", nargs=-1, required=True, shell_complete=complete_source)
@_BACKEND_OPTION
@click.option("--profile", default=None, help="Launch profile, for a gog game.")
@click.option("--conf", is_flag=True, default=False, help="Show only dosemu.conf.")
@click.option("--userhook", is_flag=True, default=False, help="Show only userhook.bat.")
@click.option(
    "--issues",
    "-i",
    is_flag=True,
    default=False,
    help="Show the [issues] block - what DOSEMU2 can't run as-is (same as `dosboxconf --issues`).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="With --issues, also show each autoexec line and what it is rewritten to.",
)
@click.option(
    "--cmdline",
    is_flag=True,
    default=False,
    help="Print the `dosemu` command `dedb run --dosemu` would run, and stop (game only).",
)
def dosemuconf(sources, backend, profile, conf, userhook, issues, verbose, cmdline):
    """Show the converted DOSEMU2 output, from dosbox.conf(s) or a game.

    SOURCES is one or more dosbox.conf paths, or a single downloaded game
    ('gog:<id>' / 'archive:<id>', or a bare id with --backend). With none
    of --conf/--userhook/--issues given, dosemu.conf and userhook.bat are
    both shown. A multi-profile GOG game with no --profile shows one
    [label] block per profile; --issues then reflects the default profile.
    --cmdline instead prints the whole `dosemu` command (needs a game).
    """
    game_ref = backend is not None or any(is_game_ref(s) for s in sources)

    if cmdline:
        if not game_ref:
            raise click.UsageError(
                "--cmdline needs a game reference (gog:/archive:), not dosbox.conf files."
            )
        if len(sources) != 1:
            raise click.UsageError("Pass a single game when using a scheme or --backend.")
        game = resolve_game(sources[0], backend, profile=profile)
        click.echo(render_cmdline(*get_backends()[game.scheme].cmdline(game, emulator="dosemu")))
        return

    if game_ref:
        if len(sources) != 1:
            raise click.UsageError("Pass a single game when using a scheme or --backend.")
        game = resolve_game(sources[0], backend, profile=profile)
        be = get_backends()[game.scheme]
        entries = be.build(game)
        if issues:
            argv, working_dir = be.dosbox_command_line(game)
            _, autoexec = parse_dosbox_argv(argv, base_dir=working_dir)
            issues_block = render_issues(autoexec, working_dir, verbose=verbose)
        else:
            issues_block = None
    else:
        paths = [existing_conf(s) for s in sources]
        target, userhook_lines = build_config(paths)
        entries = [("default", target.model_dump_dosemurc(), userhook_lines)]
        if issues:
            _, autoexec = parse_dosbox_confs(paths)
            issues_block = render_issues(autoexec, None, verbose=verbose)
        else:
            issues_block = None

    click.echo(render(entries, conf=conf, userhook=userhook, issues_block=issues_block))


commands = [import_target, dosemuconf]
