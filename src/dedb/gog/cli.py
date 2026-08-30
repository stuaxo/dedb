"""Click commands contributed by the gog app: `downloadgog` (bulk library
download) and `listgog` (owned-games list). Everything else is a generic
target-driven command - see dedb.verbs and dedb.gog.backend."""

import click

from ..core import get_download_dir, get_settings, require_download_dir
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


commands = [downloadgog, listgog]
