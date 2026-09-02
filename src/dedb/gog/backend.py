"""GOG backend: `gog://<gamename>` targets.

Registered into the dedb.core registry; imported by dedb.core.get_backends().
The runner / importer imports are function-local to keep
dedb.core -> dedb.gog.backend import-light and cycle-free.
"""

from dataclasses import dataclass

from ..core import BackendBase, Target, register_backend
from .layout import GogLayout


@register_backend("gog")
@dataclass(frozen=True)
class GogBackend(BackendBase):
    scheme: str = "gog"
    supports_profile: bool = True
    layout_cls = GogLayout
    runner_module = "dedb.gog.runner"

    def _downloader(self):
        from .downloader import GogDownloader

        return GogDownloader()

    def _import(self, layout, target: Target, output_dir, *, force):
        from .importer import import_gog_game

        import_gog_game(layout, output_dir, profile=target.profile, force=force)

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
