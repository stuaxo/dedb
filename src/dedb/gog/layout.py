"""Filesystem layout for one game under <download_dir>/gog/ (see
dedb.core.require_download_dir):

    <download_dir>/gog/<gamename>/
        installer/       setup_*.exe etc. - kept only with --keep
        metadata.json     cached GOG dependency metadata, under a "gog" key
        game/             innoextract output
        dosemu/            dosemu.conf + userhook.bat, once converted - one
                             pair per GOG launch profile (see gog.profiles):
                             the default profile's pair is unsuffixed,
                             others are dosemu_<slug>.conf/userhook_<slug>.bat
        dosemu_local/       DOSEMU2's own bootstrap/local dir for this game

Centralizes the paths that downloader.py, importer.py, runner.py, and
cli.py all otherwise need to reconstruct independently.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameLayout:
    download_dir: Path
    gamename: str

    @property
    def dir(self) -> Path:
        return self.download_dir / self.gamename

    @property
    def installer(self) -> Path:
        return self.dir / "installer"

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
        return self.dosemu_conf_for(None)

    @property
    def dosemu_local(self) -> Path:
        return self.dir / "dosemu_local"

    def dosemu_conf_for(self, slug: str | None) -> Path:
        return self.dosemu / (f"dosemu_{slug}.conf" if slug else "dosemu.conf")

    def userhook_for(self, slug: str | None) -> Path:
        return self.dosemu / (f"userhook_{slug}.bat" if slug else "userhook.bat")

    def is_downloaded(self) -> bool:
        return self.game.is_dir() and any(self.game.iterdir())

    def is_converted(self, slug: str | None = None) -> bool:
        return self.dosemu_conf_for(slug).is_file()
