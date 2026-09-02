"""Filesystem layout for one item under <download_dir>/archive/:

    <download_dir>/archive/<identifier>/
        download/          the fetched .zip - deleted unless --keep
        metadata.json      cached item metadata (see dedb.archive.models)
        game/              extracted game files
        dosemu/            dosemu.conf + userhook.bat, once converted
        dosemu_local/      DOSEMU2's own bootstrap/local dir

Mirrors `dedb.gog.layout.GameLayout` without launch profiles (an item
has one launch mode).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameLayout:
    download_dir: Path
    identifier: str

    @property
    def dir(self) -> Path:
        return self.download_dir / self.identifier

    @property
    def download(self) -> Path:
        return self.dir / "download"

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
    def userhook(self) -> Path:
        return self.dosemu / "userhook.bat"

    @property
    def dosemu_local(self) -> Path:
        return self.dir / "dosemu_local"

    def is_downloaded(self) -> bool:
        return self.game.is_dir() and any(self.game.iterdir())

    def is_converted(self) -> bool:
        return self.dosemu_conf.is_file()
