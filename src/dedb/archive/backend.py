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
        from ..core import GameMetadataFile, LaunchProfile, LocalGame

        layout = self.layout(identifier)
        envelope = GameMetadataFile.read_or_none(layout.metadata_json)
        profiles = [LaunchProfile(slug=None, name="default", is_default=True)]
        converted = layout.is_converted()

        if envelope is None:
            return LocalGame(
                scheme="archive",
                identifier=identifier,
                launch_profiles=profiles,
                converted=converted,
            )

        if envelope.classification is None:
            # A migrated v1 file kept the raw "emulator" field but no lifted
            # classification (title/year _from_v1 already handles).
            emulator = str(envelope.source.get("emulator", "")).lower()
            envelope.classification = "dosbox" if emulator == "dosbox" else None
        return envelope.as_local_game(converted=converted, launch_profiles=profiles)

    def _import(self, layout, target: Target, output_dir, *, force):
        from .importer import import_archive_game

        import_archive_game(layout, output_dir, force=force)

    def build(self, target: Target):
        from .importer import build_archive_game

        config, userhook_lines = build_archive_game(self.layout(target.identifier))
        return [("default", config.model_dump_dosemurc(), userhook_lines)]
