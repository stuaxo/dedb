"""Filesystem-layout properties shared by every backend's ``GameLayout``.

Each downloaded game/item lives under ``<download_dir>/<scheme>/<key>/``.
`LayoutPaths` builds the common paths off ``self.dir``; each backend's
`layout.GameLayout` is a frozen dataclass that mixes this in, declares its
own id field, and adds any source-specific paths.
"""

from pathlib import Path


class LayoutPaths:
    dir: Path  # provided by the concrete dataclass

    @property
    def game(self) -> Path:
        return self.dir / "game"

    @property
    def metadata_json(self) -> Path:
        return self.dir / "metadata.json"

    @property
    def dosemu(self) -> Path:
        return self.dir / "dosemu"

    @property
    def dosemu_conf(self) -> Path:
        return self.dosemu / "dosemu.conf"

    @property
    def dosemu_local(self) -> Path:
        return self.dir / "dosemu_local"

    def is_downloaded(self) -> bool:
        return self.game.is_dir() and any(self.game.iterdir())

    def is_converted(self) -> bool:
        return self.dosemu_conf.is_file()
