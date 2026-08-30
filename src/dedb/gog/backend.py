"""GOG backend: `gog://<gamename>` targets.

Registered into dedb.backends; imported by dedb.core.get_backends(). Every
method delegates to this package's existing runner/importer/layout - the
imports are function-local to keep dedb.core -> dedb.gog.backend import-light
and cycle-free.
"""

from dataclasses import dataclass

from ..backends import BackendBase, Target, register_backend


@register_backend("gog")
@dataclass(frozen=True)
class GogBackend(BackendBase):
    scheme: str = "gog"
    supports_profile: bool = True

    def layout(self, identifier: str):
        from ..core import require_download_dir
        from .layout import GameLayout

        return GameLayout(require_download_dir("gog"), identifier)

    def ensure_downloaded(self, identifier, *, keep, refresh_metadata, redownload):
        from ..core import require_download_dir
        from .runner import ensure_downloaded

        return ensure_downloaded(
            identifier,
            require_download_dir("gog"),
            keep=keep,
            refresh_metadata=refresh_metadata,
            redownload=redownload,
        )

    def run(self, target: Target, layout, *, emulator, extra_args, verbose):
        from .runner import run_dosbox, run_dosemu

        launch = run_dosbox if emulator == "dosbox" else run_dosemu
        return launch(layout, target.profile, extra_args, verbose)

    def convert(self, target: Target, *, output_dir=None, profile=None, force=False):
        from .importer import import_gog_game

        layout = self.layout(target.identifier)
        import_gog_game(layout, output_dir, profile=profile, force=force)
        return output_dir or layout.dosemu
