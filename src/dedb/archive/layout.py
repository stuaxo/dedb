"""``<download_dir>/archive/<identifier>/`` layout - see `dedb.core.layout.LayoutPaths`.

    download/          the fetched .zip - deleted unless --keep
    metadata.json      cached item metadata (see dedb.archive.models)
    game/              extracted game files
    dosemu/            dosemu.conf + userhook.bat, once converted
    dosemu_local/      DOSEMU2's own bootstrap/local dir

Mirrors `dedb.gog.layout.GogLayout` without per-profile file naming (an
item has a single launch profile).
"""

from dataclasses import dataclass
from pathlib import Path

from ..core.layout import LayoutPaths


@dataclass(frozen=True)
class ArchiveLayout(LayoutPaths):
    download_dir: Path
    identifier: str

    @property
    def dir(self) -> Path:
        return self.download_dir / self.identifier

    @property
    def download(self) -> Path:
        """The fetched .zip - `staging`."""
        return self.dir / "download"

    staging = download

    @property
    def userhook(self) -> Path:
        return self.dosemu / "userhook.bat"
