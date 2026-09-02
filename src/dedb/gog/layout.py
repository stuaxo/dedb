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
        """The extracted GOG installer (setup_*.exe etc.) - `staging`."""
        return self.dir / "installer"

    staging = installer

    # The one place the per-profile file-naming rule lives: the default
    # profile's pair is unsuffixed, every other profile's is
    # <stem>_<slug>.<ext> (see the module docstring). gog.importer and
    # gog.runner both name files through here.
    def _profile_file(self, stem: str, ext: str, slug: str | None) -> Path:
        return self.dosemu / (f"{stem}_{slug}.{ext}" if slug else f"{stem}.{ext}")

    def dosemu_conf_for(self, slug: str | None) -> Path:
        return self._profile_file("dosemu", "conf", slug)

    def userhook_for(self, slug: str | None) -> Path:
        return self._profile_file("userhook", "bat", slug)

    def is_converted(self, slug: str | None = None) -> bool:
        return self.dosemu_conf_for(slug).is_file()
