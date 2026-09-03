"""GOG backend: `gog://<gamename>` targets.

Registered into the dedb.core registry; imported by dedb.core.get_backends().
``runner_module`` / ``downloader_module`` are dotted strings, and the
importer imports are function-local, to keep dedb.core -> dedb.gog.backend
import-light and cycle-free.
"""

import json
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
    downloader_module = "dedb.gog.downloader"

    def local_game(self, identifier: str):
        from ..core import GameMetadataFile, LaunchProfile, LocalGame
        from .profiles import launch_profiles

        layout = self.layout(identifier)
        envelope = GameMetadataFile.read_or_none(layout.metadata_json)
        converted = layout.is_converted()

        if envelope and envelope.launch_profiles:
            profiles = None  # the envelope already carries them
        elif layout.is_downloaded():
            profiles = launch_profiles(layout.game)  # migrated/legacy file: re-derive
        else:
            profiles = [LaunchProfile(slug=None, name="default", is_default=True)]

        if envelope is None:
            return LocalGame(
                scheme="gog",
                identifier=identifier,
                launch_profiles=profiles,
                converted=converted,
            )
        return envelope.as_local_game(converted=converted, launch_profiles=profiles)

    def completion_ids(self):
        from .client import OWNED_GAMES_CACHE_PATH  # local: matches the other methods here

        ids = dict(super().completion_ids())
        try:
            for game in json.loads(OWNED_GAMES_CACHE_PATH.read_text()):
                ids.setdefault(game["gamename"], "owned")
        except (OSError, ValueError, KeyError, TypeError):
            pass  # no cache yet, or an unreadable one - downloads still complete
        return sorted(ids.items())

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

    def dosbox_command_line(self, target: Target):
        from .runner import dosbox_conf_argv

        layout = self.layout(target.identifier)
        layout.require_downloaded("gog")
        return dosbox_conf_argv(layout, target)
