"""Click commands contributed by the archive app.

All four are now deprecated aliases for the generic `dedb run|download|
import|rm archive://<id>` commands; they still work (and still accept a
bare identifier or a full archive.org item URL) but print a deprecation
warning and delegate to the shared code path.
"""

from pathlib import Path

import click

from .client import parse_identifier


def _warn(name: str, verb: str) -> None:
    click.echo(
        f"warning: `{name}` is deprecated - use `dedb {verb} archive://<id>` instead.", err=True
    )


def _archive_target(item: str):
    from ..backends import resolve

    return resolve(f"archive://{parse_identifier(item)}")


def _archive_backend():
    from ..core import get_backends

    return get_backends()["archive"]


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
    """Deprecated alias for `dedb download archive://<item>` - see that command."""
    _warn("downloadarchive", "download")
    target = _archive_target(item)
    _archive_backend().ensure_downloaded(
        target.identifier, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
    )
    click.echo(f"Downloaded '{target.identifier}' (archive)")


@click.command("importarchive")
@click.argument("item")
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write dosemu.conf and userhook.bat into.",
)
@click.option("--force", "-f", is_flag=True, default=False, help="Overwrite OUTPUT_DIR if it exists.")
@click.option(
    "--refreshconf",
    is_flag=True,
    default=False,
    help="Regenerate the conf for an already-downloaded item (implies --force; skips if not downloaded).",
)
@click.option("--dumpconf", is_flag=True, default=False, help="Print the dosemu.conf instead of writing.")
@click.option(
    "--dumpuserhook", is_flag=True, default=False, help="Print the userhook.bat instead of writing."
)
def importarchive(
    item: str,
    output_dir: Path | None,
    force: bool,
    refreshconf: bool,
    dumpconf: bool,
    dumpuserhook: bool,
) -> None:
    """Deprecated alias for `dedb import archive://<item>` - see that command."""
    _warn("importarchive", "import")
    from ..verbs import _do_import

    _do_import(
        _archive_target(item),
        _archive_backend(),
        output_dir=output_dir,
        force=force,
        refreshconf=refreshconf,
        dumpconf=dumpconf,
        dumpuserhook=dumpuserhook,
    )


@click.command("runarchive")
@click.argument("item")
@click.argument("emulator_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--dosbox", "use_dosbox", is_flag=True, default=False, help="Run the item in DOSBox.")
@click.option("--dosemu", "use_dosemu", is_flag=True, default=False, help="Run the item in DOSEMU2.")
@click.option("--keep", is_flag=True, default=False, help="Keep the downloaded archive if a download is needed.")
@click.option(
    "--refreshmetadata",
    "-r",
    "refresh_metadata",
    is_flag=True,
    default=False,
    help="Re-fetch archive.org item metadata if a download is needed.",
)
@click.option(
    "--redownload",
    is_flag=True,
    default=False,
    help="Re-download and re-extract the item even if it's already downloaded.",
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Print the command line before launching."
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
    """Deprecated alias for `dedb run archive://<item>` - see that command.

    Anything after a `--` is passed straight through to the emulator.
    """
    _warn("runarchive", "run")
    from ..verbs import _require_one_emulator, _run

    emulator = _require_one_emulator(use_dosbox, use_dosemu)
    _run(
        _archive_target(item),
        _archive_backend(),
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
    """Deprecated alias for `dedb rm archive://<item>` - see that command."""
    _warn("rmarchive", "rm")
    _archive_backend().remove(parse_identifier(item), assume_yes=yes)


commands = [downloadarchive, importarchive, runarchive, rmarchive]
