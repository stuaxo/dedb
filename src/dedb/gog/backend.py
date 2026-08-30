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
        from ..core import ensure_download_dir
        from .runner import ensure_downloaded

        return ensure_downloaded(
            identifier,
            ensure_download_dir("gog"),
            keep=keep,
            refresh_metadata=refresh_metadata,
            redownload=redownload,
        )

    def run(self, target: Target, layout, *, emulator, extra_args, verbose):
        from .runner import run_dosbox, run_dosemu

        launch = run_dosbox if emulator == "dosbox" else run_dosemu
        return launch(layout, target.profile, extra_args, verbose)

    def convert(self, target: Target, *, output_dir=None, force=False):
        from .importer import import_gog_game

        layout = self.layout(target.identifier)
        import_gog_game(layout, output_dir, profile=target.profile, force=force)
        return output_dir or layout.dosemu

    def build(self, target: Target):
        from .importer import build_gog_game

        results = build_gog_game(self.layout(target.identifier), profile=target.profile)
        return [
            (label, config.model_dump_dosemurc(), userhook_lines)
            for label, (_conf_files, config, userhook_lines) in results.items()
        ]

    def dosbox_sources(self, target: Target):
        from .profiles import get_conf_files, get_working_dir

        game = self.layout(target.identifier).game
        return get_conf_files(game, target.profile), get_working_dir(game, target.profile)
