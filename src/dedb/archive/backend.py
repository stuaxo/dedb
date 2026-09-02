"""archive.org backend: `archive:<id>` targets (and full item URLs via
`identifier_from_url`). No launch profiles. See `dedb.gog.backend`.
"""

from dataclasses import dataclass

import click

from ..backends import BackendBase, Target, register_backend


@register_backend("archive")
@dataclass(frozen=True)
class ArchiveBackend(BackendBase):
    scheme: str = "archive"
    supports_profile: bool = False

    def identifier_from_url(self, url: str):
        from .client import _ITEM_URL_RE

        match = _ITEM_URL_RE.match(url)
        return match.group(1) if match else None

    def layout(self, identifier: str):
        from ..core import require_download_dir
        from .layout import GameLayout

        return GameLayout(require_download_dir("archive"), identifier)

    def ensure_downloaded(self, identifier, *, keep, refresh_metadata, redownload):
        from ..core import ensure_download_dir
        from .runner import ensure_downloaded

        return ensure_downloaded(
            identifier,
            ensure_download_dir("archive"),
            keep=keep,
            refresh_metadata=refresh_metadata,
            redownload=redownload,
        )

    def run(self, target: Target, layout, *, emulator, extra_args, verbose):
        if target.profile is not None:
            raise click.ClickException("archive:// targets don't support --profile.")
        from .runner import run_dosbox, run_dosemu

        launch = run_dosbox if emulator == "dosbox" else run_dosemu
        return launch(layout, extra_args, verbose)

    def convert(self, target: Target, *, output_dir=None, force=False):
        from .importer import import_archive_game

        layout = self.layout(target.identifier)
        import_archive_game(layout, output_dir, force=force)
        return output_dir or layout.dosemu

    def build(self, target: Target):
        from .importer import build_archive_game

        config, userhook_lines = build_archive_game(self.layout(target.identifier))
        return [("default", config.model_dump_dosemurc(), userhook_lines)]
