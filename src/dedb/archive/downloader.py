"""Download and extract archive.org items. See `GameLayout` for the
on-disk layout."""

import shutil
import zipfile
from pathlib import Path

import click
from internetarchive import download as ia_download

from .client import FETCH_ERRORS, NotDosItemError
from .layout import GameLayout
from .metadata import get_metadata
from .models import ArchiveMetadata, GameMetadataFile


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Extract zip_path into dest, refusing any member that escapes dest
    (zip slip)."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not target.is_relative_to(dest):
                raise click.ClickException(
                    f"Refusing to extract '{member.filename}' outside {dest}"
                )
        zf.extractall(dest)


def _download(identifier: str, filename: str, dest_dir: Path) -> None:
    """Fetch one file from an item into dest_dir (flat), retrying
    transient failures."""
    errors = ia_download(
        identifier,
        files=[filename],
        destdir=str(dest_dir),
        no_directory=True,
        retries=3,
    )
    if errors:
        raise click.ClickException(
            f"Could not download '{filename}' from archive.org item '{identifier}'"
        )


def _write_metadata_file(layout: GameLayout, metadata: ArchiveMetadata) -> None:
    metadata_file = GameMetadataFile(archive=metadata)
    layout.metadata_json.write_text(metadata_file.model_dump_json(indent=2))


def _get_metadata_or_die(identifier: str, *, refresh: bool) -> ArchiveMetadata:
    try:
        return get_metadata(identifier, refresh=refresh)
    except NotDosItemError as exc:
        raise click.ClickException(str(exc)) from exc
    except (LookupError, *FETCH_ERRORS) as exc:
        raise click.ClickException(
            f"Could not fetch archive.org metadata for '{identifier}': {exc}"
        ) from exc


def download_and_extract(
    identifier: str,
    download_dir: Path,
    *,
    keep: bool = False,
    refresh: bool = False,
    redownload: bool = False,
) -> None:
    layout = GameLayout(download_dir, identifier)

    if redownload and layout.is_downloaded():
        print(f"Removing existing download: {identifier}")
        shutil.rmtree(layout.game, ignore_errors=True)
        shutil.rmtree(layout.download, ignore_errors=True)
        # Derived from the extracted files - drop it so the next --dosemu
        # run regenerates it.
        shutil.rmtree(layout.dosemu, ignore_errors=True)

    if layout.is_downloaded():
        print(f"Skipping: {identifier} (already downloaded)")
        if refresh or not layout.metadata_json.is_file():
            _write_metadata_file(layout, _get_metadata_or_die(identifier, refresh=refresh))
        return

    metadata = _get_metadata_or_die(identifier, refresh=refresh)
    if metadata.emulator.lower() != "dosbox":
        raise click.ClickException(
            f"'{identifier}' is an archive.org '{metadata.emulator}' item, not DOSBox - not supported."
        )
    if metadata.emulator_ext != "zip":
        raise click.ClickException(
            f"'{identifier}' ships a .{metadata.emulator_ext} archive - only .zip items are supported so far."
        )

    layout.dir.mkdir(parents=True, exist_ok=True)
    layout.download.mkdir(parents=True, exist_ok=True)
    archive_path = layout.download / metadata.download_filename

    print(f"Downloading: {identifier}")
    _download(identifier, metadata.download_filename, layout.download)

    print(f"Extracting: {identifier}")
    layout.game.mkdir(parents=True, exist_ok=True)
    _safe_extract(archive_path, layout.game)

    _write_metadata_file(layout, metadata)

    if not keep:
        shutil.rmtree(layout.download, ignore_errors=True)
