"""Download + extract one GOG game (`GogDownloader`) and the helpers that
support it. See GogLayout for the on-disk directory structure."""

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import click

from ..core import Downloader, GameMetadataFile
from ..dosbox.parser import parse_dosbox_confs
from ..shims.autoexec import resolve_mounts
from .client import FETCH_ERRORS, GOGClient
from .gameinfo import parse_profiles
from .layout import GogLayout
from .metadata import get_metadata
from .profiles import (
    launch_profiles,
    legacy_find_confs,
    resolve_conf_files,
    resolve_working_dir,
    valid_profiles,
)


def find_installer_exe(installer_dir: Path) -> Path | None:
    matches = sorted(installer_dir.glob("setup_*.exe"))
    return matches[0] if matches else None


def local_dosbox_status(layout: GogLayout) -> str | None:
    """Check an extracted game's files for a DOSBox bundle. Authoritative
    when available, since these are the actual installer contents. Returns
    None if the game hasn't been extracted locally yet."""
    if not layout.is_downloaded():
        return None
    for path in layout.game.rglob("*"):
        if "dosbox" in path.name.lower():
            return "dosbox"
    return "none"


def merge_support_save_data(layout: GogLayout) -> None:
    """GOG's installer natively lays game/__support/save/* onto the install
    root itself, via its InnoSetup [Code] script - innoextract can't
    execute that script, so we merge those files onto the game root here
    instead, ourselves. Never overwrites a file that's already present."""
    save_dir = layout.game / "__support" / "save"
    if not save_dir.is_dir():
        return
    for src in save_dir.rglob("*"):
        if src.is_dir():
            continue
        dest = layout.game / src.relative_to(save_dir)
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)


def create_missing_mount_dirs(layout: GogLayout) -> None:
    """GOG's installer natively creates any directory a game's autoexec
    MOUNTs (e.g. Dungeon Keeper's cloud-save overlay target) via its
    InnoSetup [Code] script - innoextract can't execute that script, so we
    create them here ourselves instead. Only ever creates empty
    directories, and only those that resolve inside the game directory."""
    profiles = valid_profiles(layout.game)
    if profiles:
        confs_by_working_dir = [
            (
                resolve_conf_files(layout.game, profile),
                resolve_working_dir(layout.game, profile) or layout.game,
            )
            for profile in profiles
        ]
    else:
        # Mirrors get_working_dir()'s own fallback: the first conf's own
        # directory, since there's no recorded workingDir to resolve.
        conf_files = legacy_find_confs(layout.game)
        confs_by_working_dir = [(conf_files, conf_files[0].parent)] if conf_files else []

    for conf_files, working_dir in confs_by_working_dir:
        _config, autoexec = parse_dosbox_confs(conf_files)
        for mount in resolve_mounts(autoexec, working_dir):
            if mount.host_path.is_relative_to(layout.game) and not mount.host_path.exists():
                mount.host_path.mkdir(parents=True, exist_ok=True)


class GogDownloader(Downloader):
    """`--merge-save/--no-merge-save` rides on the instance; pass
    `product_ids` (a `{gamename: product_id}` map) to skip a per-game GOG
    library lookup during a bulk `downloadgog`."""

    def __init__(
        self,
        layout: GogLayout,
        *,
        product_ids: dict[str, str] | None = None,
        merge_save: bool = True,
    ) -> None:
        super().__init__(layout)
        self._product_ids = product_ids
        self.merge_save = merge_save
        self._product_id: str | None = None

    def _prepare(self, *, refresh: bool) -> None:
        layout = self.layout
        if self._product_ids is not None:
            product_id = self._product_ids.get(layout.name)
        else:
            client = GOGClient()
            product_id = next(
                (g.product_id for g in client.get_list() if g.gamename == layout.name), None
            )
        if product_id is None:
            raise click.ClickException(f"'{layout.name}' not found in your GOG library")
        self._product_id = product_id

    def _fetch(self) -> bool:
        layout = self.layout
        # lgogdownloader always nests its output under a game-id directory of
        # its own; download into a holding dir and flatten that into installer/.
        holding_dir = layout.dir / ".installer_download"
        holding_dir.mkdir(parents=True, exist_ok=True)

        GOGClient().download(layout.name, holding_dir)

        downloaded_dir = holding_dir / layout.name
        if not downloaded_dir.is_dir():
            shutil.rmtree(holding_dir, ignore_errors=True)
            print(f"No game found matching '{layout.name}' in your GOG library - skipping")
            return False

        layout.installer.mkdir(parents=True, exist_ok=True)
        for item in downloaded_dir.iterdir():
            shutil.move(str(item), layout.installer / item.name)
        shutil.rmtree(holding_dir, ignore_errors=True)

        if find_installer_exe(layout.installer) is None:
            print(f"No .exe found in {layout.installer}")
            return False
        return True

    def _extract(self) -> None:
        layout = self.layout
        installer_exe = find_installer_exe(layout.installer)
        subprocess.run(["innoextract", "-d", str(layout.game), str(installer_exe)], check=True)

    def _post_extract(self) -> None:
        if self.merge_save:
            merge_support_save_data(self.layout)
        create_missing_mount_dirs(self.layout)

    def _write_metadata(self, *, refresh: bool) -> None:
        """metadata.json records the dependency/classification info and the
        launch profiles, with the raw GogMetadata (playTasks included)
        kept under ``source``."""
        layout = self.layout
        try:
            metadata = get_metadata(layout.name, self._product_id, refresh=refresh)
        except FETCH_ERRORS as exc:
            print(f"Could not fetch metadata for {layout.name}: {exc}")
            return
        profiles = parse_profiles(layout.game)
        envelope = GameMetadataFile(
            scheme="gog",
            identifier=layout.name,
            classification=metadata.classification,
            downloaded_at=datetime.now(timezone.utc),
            launch_profiles=launch_profiles(layout.game),
            source=metadata.model_copy(update={"profiles": profiles}).model_dump(mode="json"),
        )
        layout.metadata_json.write_text(envelope.model_dump_json(indent=2))


def make_downloader(layout: GogLayout) -> GogDownloader:
    """The backend seam (see ``BackendBase.downloader_module``)."""
    return GogDownloader(layout)
