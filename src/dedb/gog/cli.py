"""Click commands contributed by the gog app: `downloadgog` (library
download) and `lsgog` (owned-games list), both acting on your GOG
library. Single games are named `gog://<id>` and driven by the generic
commands - see dedb.dedb.verbs and dedb.gog.backend."""

import click

from ..core import ensure_download_dir, get_settings
from .classify import classify_owned_games
from .client import GOGClient, OfflineError
from .downloader import GogDownloader
from .layout import GogLayout


@click.command("downloadgog")
@click.option(
    "--keep", is_flag=True, default=False, help="Keep the installer/ directory after extracting."
)
@click.option(
    "--game",
    "game_id",
    default=None,
    help="Download only this game id.",
)
@click.option(
    "--all",
    "all_games",
    is_flag=True,
    default=False,
    help="Download every owned game classified as DOSBox-based.",
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
    help=(
        "--no-merge-save: leave bundled save files under game/__support/save/ "
        "instead of copying them onto the game root the way GOG's installer would."
    ),
)
def downloadgog(
    keep: bool,
    game_id: str | None,
    all_games: bool,
    refresh_metadata: bool,
    redownload: bool,
    merge_save: bool,
) -> None:
    """Download and extract DOSBox-based owned games from GOG.

    Pass --game for a single game, or --all for every owned game
    classified as DOSBox-based (see `lsgog`).
    """
    download_dir = ensure_download_dir("gog")

    client = GOGClient()
    games = client.get_list()
    product_id_by_name = {g.gamename: g.product_id for g in games}

    if game_id:
        targets = [game_id]
    elif all_games:
        status = classify_owned_games(games, download_dir, refresh=refresh_metadata)
        targets = sorted(name for name, s in status.items() if s.classification == "dosbox")
    else:
        raise click.UsageError(
            "Nothing to download. Pass --game <id>, or --all for every DOSBox-based owned game."
        )

    click.echo(f"Using download directory: {download_dir}")
    downloader = GogDownloader(product_ids=product_id_by_name, merge_save=merge_save)
    for gamename in targets:
        click.echo("-" * 40)
        if gamename not in product_id_by_name:
            click.echo(f"'{gamename}' not found in your GOG library - skipping")
            continue
        downloader.ensure(
            GogLayout(download_dir, gamename),
            keep=keep,
            refresh_metadata=refresh_metadata,
            redownload=redownload,
        )

    click.echo("-" * 40)
    click.echo(f"Done. Games extracted to {download_dir}/<game>/game/")


@click.command("lsgog")
@click.option(
    "-1",
    "names_only",
    is_flag=True,
    default=False,
    help="Just `gog:<id>` per line - no classification column.",
)
@click.option(
    "--dos/--all",
    "dos_only",
    default=True,
    help="--dos (default): only DOSBox-based games. --all: every owned game.",
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
    help="Don't contact GOG at all - use only local files and cached metadata.",
)
@click.option(
    "--verbose",
    "-v",
    "verbose",
    is_flag=True,
    default=False,
    help="Print each network request to GOG as it happens.",
)
def lsgog(
    names_only: bool, dos_only: bool, refresh_metadata: bool, offline: bool, verbose: bool
) -> None:
    """List owned GOG games and whether they look DOSBox-based, without downloading anything."""
    if offline and refresh_metadata:
        raise click.UsageError("--offline and --refreshmetadata can't be used together.")

    try:
        client = GOGClient()
        games = sorted(client.get_list(verbose=verbose, offline=offline), key=lambda g: g.gamename)
    except OfflineError as exc:
        raise click.ClickException(str(exc)) from exc

    # Bare names + --all needs no classification; every other combination
    # does, either to filter to dos_only or to show it in the listing.
    status = None
    if dos_only or not names_only:
        status = classify_owned_games(
            games,
            get_settings().download_dir_for("gog"),
            refresh=refresh_metadata,
            verbose=verbose,
            offline=offline,
        )
        if dos_only:
            games = [g for g in games if status[g.gamename].classification == "dosbox"]

    if names_only:
        for game in games:
            click.echo(game.target)
        return

    for game in games:
        s = status[game.gamename]
        detail = s.source if dos_only else f"{s.classification} ({s.source})"
        click.echo(f"{game.target:<50} {detail}")


commands = [downloadgog, lsgog]
