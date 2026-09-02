"""GOG backend: `gog://<gamename>` targets.

Registered into the dedb.core registry; imported by dedb.core.get_backends().
The runner / importer imports are function-local to keep
dedb.core -> dedb.gog.backend import-light and cycle-free.
"""

from dataclasses import dataclass

from ..core import BackendBase, Target, register_backend
from .layout import GameLayout


@register_backend("gog")
@dataclass(frozen=True)
class GogBackend(BackendBase):
    scheme: str = "gog"
    supports_profile: bool = True
    layout_cls = GameLayout

    def _downloader(self):
        from .downloader import GogDownloader

        return GogDownloader()

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
