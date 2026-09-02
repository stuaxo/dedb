"""Download and extract archive.org items. See `ArchiveLayout` for the
on-disk layout."""

import zipfile
from pathlib import Path

import click
from internetarchive import download as ia_download

from ..core import Downloader
from .client import FETCH_ERRORS, NotDosItemError
from .metadata import get_metadata
from .models import ArchiveMetadata, GameMetadataFile


def _extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract zip_path into dest."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)


def _fetch_file(identifier: str, filename: str, dest_dir: Path) -> None:
    """Fetch one file from an item into dest_dir (flat), retrying transient failures."""
    errors = ia_download(
        identifier, files=[filename], destdir=str(dest_dir), no_directory=True, retries=3
    )
    if errors:
        raise click.ClickException(
            f"Could not download '{filename}' from archive.org item '{identifier}'"
        )


class ArchiveDownloader(Downloader):
    def _prepare(self, layout, *, refresh: bool) -> ArchiveMetadata:
        try:
            metadata = get_metadata(layout.name, refresh=refresh)
        except NotDosItemError as exc:
            raise click.ClickException(str(exc)) from exc
        except (LookupError, *FETCH_ERRORS) as exc:
            raise click.ClickException(
                f"Could not fetch archive.org metadata for '{layout.name}': {exc}"
            ) from exc

        if metadata.emulator.lower() != "dosbox":
            raise click.ClickException(
                f"'{layout.name}' is an archive.org '{metadata.emulator}' item, "
                "not DOSBox - not supported."
            )
        if metadata.emulator_ext != "zip":
            raise click.ClickException(
                f"'{layout.name}' ships a .{metadata.emulator_ext} archive - "
                "only .zip items are supported so far."
            )
        return metadata

    def _fetch(self, layout, metadata: ArchiveMetadata) -> None:
        layout.download.mkdir(parents=True, exist_ok=True)
        _fetch_file(layout.name, metadata.download_filename, layout.download)

    def _extract(self, layout, metadata: ArchiveMetadata) -> None:
        _extract_zip(layout.download / metadata.download_filename, layout.game)

    def _write_metadata(self, layout, metadata: ArchiveMetadata, *, refresh: bool) -> None:
        layout.metadata_json.write_text(
            GameMetadataFile(archive=metadata).model_dump_json(indent=2)
        )
