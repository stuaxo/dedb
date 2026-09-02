"""Download and extract archive.org items. See `ArchiveLayout` for the
on-disk layout."""

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click

from ..core import Downloader, GameMetadataFile, LaunchMode
from .client import FETCH_ERRORS, ArchiveClient, NotDosItemError
from .metadata import get_metadata
from .models import ArchiveMetadata


def _extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract zip_path into dest."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)


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
        ArchiveClient().download(layout.name, metadata.download_filename, layout.download)

    def _extract(self, layout, metadata: ArchiveMetadata) -> None:
        _extract_zip(layout.download / metadata.download_filename, layout.game)

    def _write_metadata(self, layout, metadata: ArchiveMetadata, *, refresh: bool) -> None:
        emulator = metadata.emulator.lower()
        envelope = GameMetadataFile(
            scheme="archive",
            identifier=layout.name,
            title=metadata.title,
            year=metadata.year,
            classification="dosbox" if emulator == "dosbox" else emulator,
            downloaded_at=datetime.now(timezone.utc),
            launch_modes=[LaunchMode(slug=None, name="default", is_default=True)],
            source=metadata.model_dump(mode="json"),
        )
        layout.metadata_json.write_text(envelope.model_dump_json(indent=2))
