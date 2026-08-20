"""Click commands contributed by the gog app."""

import sys
from pathlib import Path

import click

from ..core import get_settings
from ..dosbox.inspector import inspect as inspect_conf
from ..settings import SETTINGS_PATH
from .classify import classify_owned_games
from .client import owned_games
from .downloader import download_and_extract
from .importer import import_gog_game
from .layout import GameLayout
from .profiles import get_conf_files
from .runner import ensure_downloaded, run_dosbox, run_dosemu


def _require_download_dir() -> Path:
    settings = get_settings()
    if settings.gog.download_dir is None:
        raise click.ClickException(
            f"gog.download_dir is not set. Add it to {SETTINGS_PATH}, e.g.:\n"
            '  [gog]\n  download_dir = "/path/to/downloads"'
        )
    return settings.gog.download_dir


@click.command("downloadgog")
@click.option("--keep", is_flag=True, default=False, help="Keep the installer/ directory after extracting.")
@click.option(
    "--game",
    "game_id",
    default=None,
    help="Download only this game id, instead of every DOSBox-classified owned game.",
)
@click.option(
    "--refresh",
    "-r",
    is_flag=True,
    default=False,
    help="Re-fetch GOG dependency metadata instead of using the cached copy.",
)
def downloadgog(keep: bool, game_id: str | None, refresh: bool) -> None:
    """Download and extract DOSBox-based owned games from GOG.

    By default, downloads every owned game classified as DOSBox-based (see
    `listgog`). Set [gog] curated_games in the dedb settings file to
    restrict this to specific games, or pass --game for just one.
    """
    download_dir = _require_download_dir()
    download_dir.mkdir(parents=True, exist_ok=True)

    games = owned_games()
    product_id_by_name = {g.gamename: g.product_id for g in games}

    if game_id:
        targets = [game_id]
    elif curated := get_settings().gog.curated_games:
        targets = curated
    else:
        status = classify_owned_games(games, download_dir, refresh=refresh)
        targets = sorted(name for name, s in status.items() if s.classification == "dosbox")

    click.echo(f"Using download directory: {download_dir}")
    for gamename in targets:
        click.echo("-" * 40)
        product_id = product_id_by_name.get(gamename)
        if product_id is None:
            click.echo(f"'{gamename}' not found in your GOG library - skipping")
            continue
        download_and_extract(gamename, product_id, download_dir, keep=keep, refresh=refresh)

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
    "--refresh",
    "-r",
    is_flag=True,
    default=False,
    help="Re-fetch GOG dependency metadata instead of using the cached copy.",
)
def listgog(output_format: str, ids_shortcut: bool, dos_only: bool, refresh: bool) -> None:
    """List owned GOG games and whether they look DOSBox-based, without downloading anything."""
    if ids_shortcut:
        output_format = "ids"

    games = sorted(owned_games(), key=lambda g: g.gamename)
    settings = get_settings()

    # ids + --all never needs classification; every other combination does,
    # either to filter down to dos_only or to display it in the table.
    status = None
    if dos_only or output_format == "table":
        status = classify_owned_games(games, settings.gog.download_dir, refresh=refresh)
        if dos_only:
            games = [g for g in games if status[g.gamename].classification == "dosbox"]

    if output_format == "ids":
        for game in games:
            click.echo(game.gamename)
        return

    curated = set(settings.gog.curated_games)

    scope = ", DOSBox-based only" if dos_only else ""
    click.echo(f"Owned Windows-platform games on GOG ({len(games)}{scope}):")
    click.echo(
        "Checking already-extracted local files first; "
        "hitting GOG's cached/build metadata only for the rest...\n"
    )

    for game in games:
        s = status[game.gamename]
        marker = "*" if game.gamename in curated else " "
        click.echo(f"  {marker} {game.gamename:<50} {s.classification} ({s.source})")

    if curated:
        click.echo("\n* = in your [gog] curated_games setting")
        mismatched = sorted(g for g in curated if status.get(g) is None or status[g].classification != "dosbox")
        if mismatched:
            click.echo("\nIn [gog] curated_games, but not confirmed DOSBox-based:")
            for gamename in mismatched:
                s = status.get(gamename)
                detail = f"{s.classification} ({s.source})" if s else "not found in your GOG library"
                click.echo(f"  - {gamename}: {detail}")
    else:
        action = "every game listed above" if dos_only else "every game marked 'dosbox' above"
        click.echo(
            f"\n`downloadgog` will download {action}. "
            "Set [gog] curated_games in the dedb settings file to restrict it to specific games."
        )


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
def importgog(game_id: str, output_dir: Path | None, profile: str | None, force: bool, refreshconf: bool) -> None:
    """Import an already-downloaded GOG game's dosbox launch profile(s) into DOSEMU2 config(s).

    Reuses the same conversion as `importdosbox`. By default, converts
    every valid launch profile (see doc/gog.md): the default profile's
    pair is written as dosemu.conf/userhook.bat, others as
    dosemu_<profile>.conf/userhook_<profile>.bat in the same directory.
    """
    layout = GameLayout(_require_download_dir(), game_id)

    if refreshconf:
        if not layout.is_downloaded():
            click.echo(f"Skipping '{game_id}' (not downloaded)")
            return
        force = True

    results = import_gog_game(layout, output_dir, profile=profile, force=force)

    target_dir = output_dir or layout.dosemu
    for label, conf_files in results.items():
        sources = ", ".join(str(f) for f in conf_files)
        click.echo(f"[{label}] Imported {sources} -> '{target_dir}'")


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
def rungog(
    game_id: str, emulator_args: tuple[str, ...], use_dosbox: bool, use_dosemu: bool, profile: str | None, keep: bool
) -> None:
    """Run a GOG game in DOSBox or DOSEMU2.

    Downloads the game first if it hasn't been downloaded yet, and for
    --dosemu, converts its dosbox.conf(s) first if that hasn't been done yet.

    Anything after a `--` is passed straight through to the emulator, e.g.
    `dedb rungog mygame --dosbox -- -fullscreen`.
    """
    if use_dosbox == use_dosemu:
        raise click.UsageError("Specify exactly one of --dosbox or --dosemu.")

    download_dir = _require_download_dir()
    layout = ensure_downloaded(game_id, download_dir, keep=keep)

    exit_code = (
        run_dosbox(layout, profile, emulator_args) if use_dosbox else run_dosemu(layout, profile, emulator_args)
    )
    if exit_code != 0:
        sys.exit(exit_code)


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
def dosboxconfgog(game_id: str, profile: str | None, autoexec: bool, sblaster: bool, gus: bool) -> None:
    """Show aspects of an already-downloaded GOG game's resolved dosbox conf(s).

    Resolves the same conf(s) `rungog --dosbox` would use for the given
    --profile (default: the primary profile). With none of -a/-s/-g given,
    all aspects are shown.
    """
    layout = GameLayout(_require_download_dir(), game_id)
    conf_files = get_conf_files(layout.game, profile)
    click.echo(inspect_conf(conf_files, autoexec=autoexec, sblaster=sblaster, gus=gus))


commands = [downloadgog, listgog, importgog, rungog, dosboxconfgog]
