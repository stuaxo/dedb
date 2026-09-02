"""``<download_dir>/archive/<identifier>/`` layout - see `dedb.layout.LayoutPaths`.

    download/          the fetched .zip - deleted unless --keep
    metadata.json      cached item metadata (see dedb.archive.models)
    game/              extracted game files
    dosemu/            dosemu.conf + userhook.bat, once converted
    dosemu_local/      DOSEMU2's own bootstrap/local dir

Mirrors `dedb.gog.layout.GameLayout` without launch profiles (an item has
one launch mode).
"""

from dataclasses import dataclass
from pathlib import Path

from ..layout import LayoutPaths


@dataclass(frozen=True)
class GameLayout(LayoutPaths):
    download_dir: Path
    identifier: str

    @property
    def dir(self) -> Path:
        return self.download_dir / self.identifier

    @property
    def download(self) -> Path:
        return self.dir / "download"

    @property
    def userhook(self) -> Path:
        return self.dosemu / "userhook.bat"
