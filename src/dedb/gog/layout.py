"""``<download_dir>/gog/<gamename>/`` layout - see `dedb.core.layout.LayoutPaths`.

    installer/         setup_*.exe etc. - kept only with --keep
    metadata.json      cached GOG dependency metadata, under a "gog" key
    game/              innoextract output
    dosemu/            dosemu.conf + userhook.bat, once converted
    dosemu_local/      DOSEMU2's own bootstrap/local dir

One dosemu.conf / userhook.bat pair per launch profile (see gog.profiles):
the default profile's is unsuffixed, others are dosemu_<slug>.conf /
userhook_<slug>.bat.
"""

from dataclasses import dataclass
from pathlib import Path

from ..core.layout import LayoutPaths


@dataclass(frozen=True)
class GogLayout(LayoutPaths):
    download_dir: Path
    gamename: str

    @property
    def dir(self) -> Path:
        return self.download_dir / self.gamename

    @property
    def installer(self) -> Path:
        return self.dir / "installer"

    def rm_installer(self) -> None:
        """Delete the downloaded installer (setup_*.exe etc.)."""
        self._safe_rmtree(self.installer)

    def dosemu_conf_for(self, slug: str | None) -> Path:
        return self.dosemu / (f"dosemu_{slug}.conf" if slug else "dosemu.conf")

    def userhook_for(self, slug: str | None) -> Path:
        return self.dosemu / (f"userhook_{slug}.bat" if slug else "userhook.bat")

    def is_converted(self, slug: str | None = None) -> bool:
        return self.dosemu_conf_for(slug).is_file()
