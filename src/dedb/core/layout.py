"""Filesystem-layout properties shared by every backend's layout class
(``GogLayout``, ``ArchiveLayout``).

Each downloaded game/item lives under ``<download_dir>/<scheme>/<key>/``.
`LayoutPaths` builds the common paths off ``self.dir``; each backend's
layout is a frozen dataclass that mixes this in, declares its own id
field (and ``download_dir``), and adds any source-specific paths.
"""

import shutil
from pathlib import Path

from .refs import long_target

# A download root with fewer parts than this - '/', '/home', a bare drive -
# is almost certainly a misconfigured download_dir, not somewhere to rmtree.
_MIN_SAFE_ROOT_PARTS = 3


class NotDownloadedError(FileNotFoundError):
    """A game's files haven't been extracted yet - the caller needs to run
    ``dedb download`` first. Reported to the user as a one-line error."""


class UnsafePathError(RuntimeError):
    """A remove target failed the download-tree safety checks (a shallow
    ``download_dir``, an item that isn't a direct child of it, a target
    outside the item dir). Reported to the user as a one-line error."""


class LayoutPaths:
    # provided by the concrete dataclass
    dir: Path
    download_dir: Path

    @property
    def name(self) -> str:
        """The game/item id - the last component of ``dir``."""
        return self.dir.name

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

    @property
    def userhook_dir(self) -> Path:
        """A dedb-owned dir holding just ``userhook.bat`` for the active
        launch. `launch_dosemu` mounts it as its own DOSEMU2 drive so the
        game directory (C:) is never written to."""
        return self.dosemu / "hook"

    @property
    def staging(self) -> Path:
        """The single download-staging dir - the fetched installer/archive,
        removed after extraction unless ``--keep``. Each backend's layout
        names it (``installer/`` for GOG, ``download/`` for archive.org)."""
        raise NotImplementedError

    def is_downloaded(self) -> bool:
        return self.game.is_dir() and any(self.game.iterdir())

    def require_downloaded(self, scheme: str) -> None:
        """Raise ``NotDownloadedError`` pointing at ``dedb download`` unless
        the game's files have already been extracted. ``scheme`` is the
        owning backend's, only needed to spell the download command."""
        if not self.is_downloaded():
            raise NotDownloadedError(
                f"'{self.name}' hasn't been downloaded yet. "
                f"Run `dedb download {long_target(scheme, self.name)}` first."
            )

    def is_converted(self) -> bool:
        return self.dosemu_conf.is_file()

    # --- removal -----------------------------------------------------------

    def _safe_rmtree(self, target: Path) -> None:
        """Delete ``target`` (the item dir or something inside it), refusing
        anything that doesn't sit safely under a real download root: a
        shallow ``download_dir``, an item dir that isn't a direct child of
        it (``..``, a slashed id, a symlink out), or a target outside the
        item dir."""
        root = self.download_dir.resolve()
        item = self.dir.resolve()
        resolved = target.resolve()
        if len(root.parts) < _MIN_SAFE_ROOT_PARTS:
            raise UnsafePathError(
                f"Refusing to touch '{root}' - download_dir looks misconfigured."
            )
        if item.parent != root:
            raise UnsafePathError(
                f"Refusing to remove under '{self.dir}' - not a single item below {root}."
            )
        if resolved != item and not resolved.is_relative_to(item):
            raise UnsafePathError(f"Refusing to remove '{target}' - outside '{self.dir}'.")
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=True)
        elif resolved.exists():
            resolved.unlink()

    def rm(self) -> None:
        """Delete the whole item directory."""
        self._safe_rmtree(self.dir)

    def rm_game(self) -> None:
        """Delete the extracted game files."""
        self._safe_rmtree(self.game)

    def rm_dosemu(self) -> None:
        """Delete the generated DOSEMU2 config(s), so the next launch regenerates them."""
        self._safe_rmtree(self.dosemu)

    def rm_staging(self) -> None:
        """Delete the download-staging dir (see ``staging``)."""
        self._safe_rmtree(self.staging)
