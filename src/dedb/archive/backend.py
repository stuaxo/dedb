"""archive.org backend: `archive://<identifier>` targets.

Also recognises full archive.org item URLs (https://archive.org/details/<id>
etc.) via identifier_from_url. archive.org items have no launch profiles, so
--profile is rejected. See dedb.gog.backend for the delegation pattern.
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
        from ..core import require_download_dir
        from .runner import ensure_downloaded

        return ensure_downloaded(
            identifier,
            require_download_dir("archive"),
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

    def convert(self, target: Target, *, output_dir=None, profile=None, force=False):
        if profile is not None:
            raise click.ClickException("archive:// targets don't support --profile.")
        from .importer import import_archive_game

        layout = self.layout(target.identifier)
        import_archive_game(layout, output_dir, force=force)
        return output_dir or layout.dosemu
