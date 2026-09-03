"""Download and extract archive.org items. See `ArchiveLayout` for the
on-disk layout."""

import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..core import Downloader, DownloadError, GameMetadataFile, LaunchProfile
from .client import FETCH_ERRORS, ArchiveClient, NotDosItemError
from .metadata import get_metadata
from .models import ArchiveMetadata


def _extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract zip_path into dest."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)


class ArchiveDownloader(Downloader):
    def __init__(self, layout) -> None:
        super().__init__(layout)
        self._metadata: ArchiveMetadata | None = None

    def _prepare(self, *, refresh: bool) -> None:
        name = self.layout.name
        try:
            metadata = get_metadata(name, refresh=refresh)
        except NotDosItemError:
            raise  # already a clean, user-facing LookupError
        except (LookupError, *FETCH_ERRORS) as exc:
            raise DownloadError(
                f"Could not fetch archive.org metadata for '{name}': {exc}"
            ) from exc

        if metadata.emulator.lower() != "dosbox":
            raise NotDosItemError(
                f"'{name}' is an archive.org '{metadata.emulator}' item, "
                "not DOSBox - not supported."
            )
        if metadata.emulator_ext != "zip":
            raise NotDosItemError(
                f"'{name}' ships a .{metadata.emulator_ext} archive - "
                "only .zip items are supported so far."
            )
        self._metadata = metadata

    def _fetch(self) -> None:
        layout = self.layout
        layout.download.mkdir(parents=True, exist_ok=True)
        ArchiveClient().download(layout.name, self._metadata.download_filename, layout.download)

    def _extract(self) -> None:
        _extract_zip(self.layout.download / self._metadata.download_filename, self.layout.game)

    def _write_metadata(self, *, refresh: bool) -> None:
        layout = self.layout
        metadata = self._metadata
        emulator = metadata.emulator.lower()
        envelope = GameMetadataFile(
            scheme="archive",
            identifier=layout.name,
            title=metadata.title,
            year=metadata.year,
            classification="dosbox" if emulator == "dosbox" else emulator,
            downloaded_at=datetime.now(timezone.utc),
            launch_profiles=[LaunchProfile(slug=None, name="default", is_default=True)],
            source=metadata.model_dump(mode="json"),
        )
        layout.metadata_json.write_text(envelope.model_dump_json(indent=2))


def make_downloader(layout) -> ArchiveDownloader:
    """The backend seam (see ``BackendBase.downloader_module``)."""
    return ArchiveDownloader(layout)
