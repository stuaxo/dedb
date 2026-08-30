"""Click commands contributed by the gog app."""

from pathlib import Path

import click

from ..core import get_download_dir, get_settings, require_download_dir
from ..dosbox.inspector import inspect as inspect_conf
from .classify import classify_owned_games
from .client import OfflineError, owned_games
from .downloader import download_and_extract


@click.command("downloadgog")
@click.option("--keep", is_flag=True, default=False, help="Keep the installer/ directory after extracting.")
@click.option(
    "--game",
    "game_id",
    default=None,
    help="Download only this game id, instead of every DOSBox-classified owned game.",
)
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch GOG dependency metadata instead of using the cached copy.",
)
@click.option(
    "--redownload",
    is_flag=True,
    default=False,
    help="Re-download and re-extract games even if they're already downloaded.",
)
@click.option(
    "--merge-save/--no-merge-save",
    "merge_save",
    default=True,
    help="--no-merge-save: don't merge game/__support/save/ onto the game root (see merge_support_save_data).",
)
def downloadgog(
    keep: bool, game_id: str | None, refresh_metadata: bool, redownload: bool, merge_save: bool
) -> None:
    """Download and extract DOSBox-based owned games from GOG.

    By default, downloads every owned game classified as DOSBox-based (see
    `listgog`). Set [gog] curated_games in the dedb settings file to
    restrict this to specific games, or pass --game for just one.
    """
    download_dir = require_download_dir("gog")
    download_dir.mkdir(parents=True, exist_ok=True)

    games = owned_games()
    product_id_by_name = {g.gamename: g.product_id for g in games}

    if game_id:
        targets = [game_id]
    elif curated := get_settings().gog.curated_games:
        targets = curated
    else:
        status = classify_owned_games(games, download_dir, refresh=refresh_metadata)
        targets = sorted(name for name, s in status.items() if s.classification == "dosbox")

    click.echo(f"Using download directory: {download_dir}")
    for gamename in targets:
        click.echo("-" * 40)
        product_id = product_id_by_name.get(gamename)
        if product_id is None:
            click.echo(f"'{gamename}' not found in your GOG library - skipping")
            continue
        download_and_extract(
            gamename,
            product_id,
            download_dir,
            keep=keep,
            refresh=refresh_metadata,
            redownload=redownload,
            merge_save=merge_save,
        )

    click.echo("-" * 40)
    click.echo(f"Done. Games extracted to {download_dir}/<game>/game/")


@click.command("listgog")
@click.option(
    "--format",
    "-F",
    "output_format",
    type=click.Choice(["table", "ids"]),
    default="table",
    help="table: human-readable classification table. ids: one game id per line.",
)
@click.option(
    "-1",
    "ids_shortcut",
    is_flag=True,
    default=False,
    help="Shortcut for --format ids (like `ls -1`).",
)
@click.option(
    "--dos/--all",
    "dos_only",
    default=True,
    help="--dos (default): only show games classified as DOSBox-based. --all: show every owned game.",
)
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch GOG dependency metadata instead of using the cached copy.",
)
@click.option(
    "--offline",
    is_flag=True,
    default=False,
    help="Don't contact GOG at all - use only local files and previously-cached metadata.",
)
@click.option(
    "--verbose",
    "-v",
    "verbose",
    is_flag=True,
    default=False,
    help="Print each network request to GOG as it happens.",
)
def listgog(
    output_format: str, ids_shortcut: bool, dos_only: bool, refresh_metadata: bool, offline: bool, verbose: bool
) -> None:
    """List owned GOG games and whether they look DOSBox-based, without downloading anything."""
    if ids_shortcut:
        output_format = "ids"
    if offline and refresh_metadata:
        raise click.UsageError("--offline and --refreshmetadata can't be used together.")

    try:
        games = sorted(owned_games(verbose=verbose, offline=offline), key=lambda g: g.gamename)
    except OfflineError as exc:
        raise click.ClickException(str(exc))
    settings = get_settings()

    # ids + --all never needs classification; every other combination does,
    # either to filter down to dos_only or to display it in the table.
    status = None
    if dos_only or output_format == "table":
        status = classify_owned_games(
            games, get_download_dir("gog"), refresh=refresh_metadata, verbose=verbose, offline=offline
        )
        if dos_only:
            games = [g for g in games if status[g.gamename].classification == "dosbox"]

    if output_format == "ids":
        for game in games:
            click.echo(game.gamename)
        return

    curated = set(settings.gog.curated_games)

    for game in games:
        s = status[game.gamename]
        marker = "*" if game.gamename in curated else " "
        detail = s.source if dos_only else f"{s.classification} ({s.source})"
        click.echo(f"{marker}{game.gamename:<50} {detail}")

    if curated:
        mismatched = sorted(g for g in curated if status.get(g) is None or status[g].classification != "dosbox")
        if mismatched:
            click.echo("\nIn [gog] curated_games, but not confirmed DOSBox-based:")
            for gamename in mismatched:
                s = status.get(gamename)
                detail = f"{s.classification} ({s.source})" if s else "not found in your GOG library"
                click.echo(f"  - {gamename}: {detail}")


@click.command("importgog")
@click.argument("game_id")
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write dosemu.conf(s) and userhook.bat(s) into. Defaults to <download_dir>/<game_id>/dosemu.",
)
@click.option(
    "--profile",
    default=None,
    help="Convert only this launch profile (name or slug - see `dedb rungog --help`). Default: every valid profile.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite OUTPUT_DIR if it already exists.",
)
@click.option(
    "--refreshconf",
    is_flag=True,
    default=False,
    help=(
        "Regenerate the DOSEMU2 conf(s) for an already-downloaded game, "
        "overwriting any existing ones (implies --force). Never downloads - "
        "games that aren't downloaded yet are skipped rather than erroring, "
        "so this is safe to loop over every game in your download directory."
    ),
)
@click.option(
    "--dumpconf",
    is_flag=True,
    default=False,
    help="Print the dosemu.conf(s) it would create instead of writing any files.",
)
@click.option(
    "--dumpuserhook",
    is_flag=True,
    default=False,
    help="Print the userhook.bat(s) it would create instead of writing any files.",
)
def importgog(
    game_id: str,
    output_dir: Path | None,
    profile: str | None,
    force: bool,
    refreshconf: bool,
    dumpconf: bool,
    dumpuserhook: bool,
) -> None:
    """Deprecated alias for `dedb import gog://<game_id>` - see that command."""
    click.echo("warning: `importgog` is deprecated - use `dedb import gog://<id>` instead.", err=True)

    from ..backends import resolve
    from ..core import get_backends
    from ..verbs import _do_import

    target = resolve(f"gog://{game_id}", profile=profile)
    _do_import(
        target,
        get_backends()["gog"],
        output_dir=output_dir,
        force=force,
        refreshconf=refreshconf,
        dumpconf=dumpconf,
        dumpuserhook=dumpuserhook,
    )


@click.command("rungog")
@click.argument("game_id")
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, default=False, help="Run the game in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, default=False, help="Run the game in DOSEMU2.")
@click.option(
    "--profile",
    default=None,
    help="Which launch profile to run (name or slug, e.g. a game's multiplayer host/client mode). Default: the game's primary profile.",
)
@click.option(
    "--keep",
    is_flag=True,
    default=False,
    help="Keep the installer/ directory if a download is needed.",
)
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch GOG dependency metadata if a download is needed (or already downloaded).",
)
@click.option(
    "--redownload",
    is_flag=True,
    default=False,
    help="Re-download and re-extract the game even if it's already downloaded.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Print the command line before launching DOSBox/DOSEMU2.",
)
def rungog(
    game_id: str,
    emulator_args: tuple[str, ...],
    use_dosbox: bool,
    use_dosemu: bool,
    profile: str | None,
    keep: bool,
    refresh_metadata: bool,
    redownload: bool,
    verbose: bool,
) -> None:
    """Deprecated alias for `dedb run gog://<game_id>` - see that command.

    Anything after a `--` is passed straight through to the emulator.
    """
    click.echo("warning: `rungog` is deprecated - use `dedb run gog://<id>` instead.", err=True)

    from ..backends import resolve
    from ..core import get_backends
    from ..verbs import _require_one_emulator, _run

    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    target = resolve(f"gog://{game_id}", profile=profile)
    _run(
        target,
        get_backends()["gog"],
        emulator=emulator,
        extra_args=emulator_args,
        verbose=verbose,
        keep=keep,
        refresh_metadata=refresh_metadata,
        redownload=redownload,
    )


@click.command("dosboxconfgog")
@click.argument("game_id")
@click.option(
    "--profile",
    default=None,
    help="Which launch profile to inspect (name or slug). Default: the game's primary profile.",
)
@click.option("--autoexec", "-a", is_flag=True, default=False, help="Show the [autoexec] commands.")
@click.option(
    "--sblaster",
    "-s",
    is_flag=True,
    default=False,
    help="Show Sound Blaster ([sblaster]) settings.",
)
@click.option("--gus", "-g", is_flag=True, default=False, help="Show Gravis Ultrasound ([gus]) settings.")
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
def dosboxconfgog(
    game_id: str,
    profile: str | None,
    autoexec: bool,
    sblaster: bool,
    gus: bool,
    issues: bool,
    verbose: bool,
) -> None:
    """Deprecated alias for `dedb dosboxconf gog://<game_id>` - see that command."""
    click.echo(
        "warning: `dosboxconfgog` is deprecated - use `dedb dosboxconf gog://<id>` instead.", err=True
    )

    from ..backends import resolve
    from ..core import get_backends

    target = resolve(f"gog://{game_id}", profile=profile)
    conf_files, working_dir = get_backends()["gog"].dosbox_sources(target)
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


@click.command("rmgog")
@click.argument("game_id")
@click.option("--yes", "-y", is_flag=True, default=False, help="Remove without prompting for confirmation.")
def rmgog(game_id: str, yes: bool) -> None:
    """Deprecated alias for `dedb rm gog://<game_id>` - see that command."""
    click.echo("warning: `rmgog` is deprecated - use `dedb rm gog://<id>` instead.", err=True)

    from ..core import get_backends

    get_backends()["gog"].remove(game_id, assume_yes=yes)


commands = [downloadgog, listgog, importgog, rungog, dosboxconfgog, rmgog]
