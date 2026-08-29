"""Filesystem layout for one item under <download_dir>/archive/ (see
dedb.core.require_download_dir):

    <download_dir>/archive/<identifier>/
        download/         the fetched .zip - deleted after extraction
                            unless --keep
        metadata.json      cached archive.org item metadata, under an
                             "archive" key (see dedb.archive.models)
        game/              extracted game files
        dosemu/            dosemu.conf + userhook.bat, once converted
        dosemu_local/      DOSEMU2's own bootstrap/local dir for this item

Mirrors dedb.gog.layout.GameLayout, minus the launch-profile support
GOG needs - an archive.org item only ever has one launch mode
(emulator_start), so there's nothing to suffix filenames by.
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
