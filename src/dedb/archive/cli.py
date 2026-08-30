"""Click commands contributed by the archive app."""

from pathlib import Path

import click

from ..core import remove_download, require_download_dir
from .client import parse_identifier
from .downloader import download_and_extract
from .importer import build_archive_game, import_archive_game
from .layout import GameLayout


@click.command("downloadarchive")
@click.argument("item")
@click.option("--keep", is_flag=True, default=False, help="Keep the downloaded archive after extracting.")
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch archive.org item metadata instead of using the cached copy.",
)
@click.option(
    "--redownload",
    is_flag=True,
    default=False,
    help="Re-download and re-extract the item even if it's already downloaded.",
)
def downloadarchive(item: str, keep: bool, refresh_metadata: bool, redownload: bool) -> None:
    """Download and extract a DOSBox-playable item from archive.org.

    ITEM is either an archive.org identifier (e.g.
    msdos_Electro_Man_1992) or a full item URL, e.g.
    https://archive.org/details/msdos_Electro_Man_1992.
    """
    identifier = parse_identifier(item)
    download_dir = require_download_dir("archive")
    download_dir.mkdir(parents=True, exist_ok=True)

    download_and_extract(
        identifier, download_dir, keep=keep, refresh=refresh_metadata, redownload=redownload
    )

    click.echo(f"Done. '{identifier}' extracted to {download_dir}/{identifier}/game/")


@click.command("importarchive")
@click.argument("item")
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write dosemu.conf and userhook.bat into. Defaults to <download_dir>/<identifier>/dosemu.",
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
        "Regenerate the DOSEMU2 conf for an already-downloaded item, "
        "overwriting any existing one (implies --force). Never downloads - "
        "an item that isn't downloaded yet is skipped rather than erroring."
    ),
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
def importarchive(
    item: str,
    output_dir: Path | None,
    force: bool,
    refreshconf: bool,
    dumpconf: bool,
    dumpuserhook: bool,
) -> None:
    """Import an already-downloaded archive.org item into a DOSEMU2 config.

    There's no dosbox.conf to convert - archive.org items only record
    which file to run (see doc/archive.md) - so this synthesizes a
    minimal one from DOSBox's own defaults instead.
    """
    identifier = parse_identifier(item)
    layout = GameLayout(require_download_dir("archive"), identifier)

    if dumpconf or dumpuserhook:
        target, userhook_lines = build_archive_game(layout)
        if dumpconf:
            click.echo(target.model_dump_dosemurc(), nl=False)
        if dumpuserhook:
            click.echo("\n".join(userhook_lines))
        return

    if refreshconf:
        if not layout.is_downloaded():
            click.echo(f"Skipping '{identifier}' (not downloaded)")
            return
        force = True

    import_archive_game(layout, output_dir, force=force)

    target_dir = output_dir or layout.dosemu
    click.echo(f"Imported '{identifier}' -> '{target_dir}'")


@click.command("runarchive")
@click.argument("item")
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, default=False, help="Run the item in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, default=False, help="Run the item in DOSEMU2.")
@click.option(
    "--keep",
    is_flag=True,
    default=False,
    help="Keep the downloaded archive if a download is needed.",
)
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch archive.org item metadata if a download is needed (or already downloaded).",
)
@click.option(
    "--redownload",
    is_flag=True,
    default=False,
    help="Re-download and re-extract the item even if it's already downloaded.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Print the command line before launching DOSBox/DOSEMU2.",
)
def runarchive(
    item: str,
    emulator_args: tuple[str, ...],
    use_dosbox: bool,
    use_dosemu: bool,
    keep: bool,
    refresh_metadata: bool,
    redownload: bool,
    verbose: bool,
) -> None:
    """Run an archive.org item in DOSBox or DOSEMU2.

    Deprecated alias for `dedb run archive://<item>` - see that command.
    ITEM may still be a bare identifier or a full archive.org item URL.
    Anything after a `--` is passed straight through to the emulator.
    """
    click.echo(
        "warning: `runarchive` is deprecated - use `dedb run archive://<item>` instead.", err=True
    )

    from ..backends import resolve
    from ..core import get_backends
    from ..verbs import _require_one_emulator, _run

    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    target = resolve(f"archive://{parse_identifier(item)}")
    _run(
        target,
        get_backends()["archive"],
        emulator=emulator,
        extra_args=emulator_args,
        verbose=verbose,
        keep=keep,
        refresh_metadata=refresh_metadata,
        redownload=redownload,
    )


@click.command("rmarchive")
@click.argument("item")
@click.option("--yes", "-y", is_flag=True, default=False, help="Remove without prompting for confirmation.")
def rmarchive(item: str, yes: bool) -> None:
    """Delete a downloaded archive.org item.

    Removes its whole directory under <download_dir>/archive/ - extracted
    game files, the converted DOSEMU2 config, and the cached
    metadata.json. The globally-cached archive.org item metadata is kept;
    use `downloadarchive --refreshmetadata` to re-fetch that.

    ITEM is an archive.org identifier or a full item URL, as for
    `downloadarchive`.
    """
    identifier = parse_identifier(item)
    remove_download(require_download_dir("archive"), identifier, assume_yes=yes)


commands = [downloadarchive, importarchive, runarchive, rmarchive]
