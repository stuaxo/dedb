"""archive.org backend: `archive:<id>` targets (and full item URLs via
`identifier_from_url`). No launch profiles. See `dedb.gog.backend`.
"""

from dataclasses import dataclass

from ..core import BackendBase, Target, register_backend
from .layout import ArchiveLayout


@register_backend("archive")
@dataclass(frozen=True)
class ArchiveBackend(BackendBase):
    scheme: str = "archive"
    supports_profile: bool = False
    layout_cls = ArchiveLayout
    runner_module = "dedb.archive.runner"

    def identifier_from_url(self, url: str):
        from .client import _ITEM_URL_RE

        match = _ITEM_URL_RE.match(url)
        return match.group(1) if match else None

    def _downloader(self):
        from .downloader import ArchiveDownloader

        return ArchiveDownloader()

    def local_game(self, identifier: str):
        from ..core import GameMetadataFile, LaunchMode, LocalGame

        layout = self.layout(identifier)
        envelope = GameMetadataFile.read_or_none(layout.metadata_json)

        title = year = classification = None
        if envelope:
            title = envelope.title or envelope.source.get("title")
            year = envelope.year or envelope.source.get("year")
            emulator = str(envelope.source.get("emulator", "")).lower()
            classification = envelope.classification or ("dosbox" if emulator == "dosbox" else None)

        return LocalGame(
            scheme="archive",
            identifier=identifier,
            title=title,
            year=year,
            classification=classification,
            downloaded_at=(envelope.downloaded_at if envelope else None),
            launch_modes=[LaunchMode(slug=None, name="default", is_default=True)],
            converted=layout.is_converted(),
        )

    def _import(self, layout, target: Target, output_dir, *, force):
        from .importer import import_archive_game

        import_archive_game(layout, output_dir, force=force)

    def build(self, target: Target):
        from .importer import build_archive_game

        config, userhook_lines = build_archive_game(self.layout(target.identifier))
        return [("default", config.model_dump_dosemurc(), userhook_lines)]
