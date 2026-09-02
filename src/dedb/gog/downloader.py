"""Download + extract one GOG game (`GogDownloader`) and the helpers that
support it. See GameLayout for the on-disk directory structure."""

import shutil
import subprocess
from pathlib import Path

import click

from ..core import Downloader
from ..dosbox.parser import parse_dosbox_confs
from ..shims.autoexec import resolve_mounts
from .client import FETCH_ERRORS, owned_games
from .gameinfo import parse_profiles
from .layout import GameLayout
from .metadata import get_metadata
from .models import GameMetadataFile
from .profiles import legacy_find_confs, resolve_conf_files, resolve_working_dir, valid_profiles


def find_installer_exe(installer_dir: Path) -> Path | None:
    matches = sorted(installer_dir.glob("setup_*.exe"))
    return matches[0] if matches else None


def local_dosbox_status(layout: GameLayout) -> str | None:
    """Check an extracted game's files for a DOSBox bundle. Authoritative
    when available, since these are the actual installer contents. Returns
    None if the game hasn't been extracted locally yet."""
    if not layout.is_downloaded():
        return None
    for path in layout.game.rglob("*"):
        if "dosbox" in path.name.lower():
            return "dosbox"
    return "none"


def merge_support_save_data(layout: GameLayout) -> None:
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


def create_missing_mount_dirs(layout: GameLayout) -> None:
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
        self, *, product_ids: dict[str, str] | None = None, merge_save: bool = True
    ) -> None:
        self._product_ids = product_ids
        self.merge_save = merge_save

    def _prepare(self, layout: GameLayout, *, refresh: bool) -> str:
        if self._product_ids is not None:
            product_id = self._product_ids.get(layout.name)
        else:
            product_id = next(
                (g.product_id for g in owned_games() if g.gamename == layout.name), None
            )
        if product_id is None:
            raise click.ClickException(f"'{layout.name}' not found in your GOG library")
        return product_id

    def _fetch(self, layout: GameLayout, product_id: str) -> bool:
        # lgogdownloader always nests its output under a game-id directory of
        # its own; download into a holding dir and flatten that into installer/.
        holding_dir = layout.dir / ".installer_download"
        holding_dir.mkdir(parents=True, exist_ok=True)
        # --include installers: without this, lgogdownloader also pulls bonus
        # content (soundtracks, wallpapers, ...), which can dwarf the installer.
        subprocess.run(
            [
                "lgogdownloader",
                "--download",
                "--game",
                f"^{layout.name}$",
                "--platform",
                "w",
                "--include",
                "installers",
            ],
            cwd=holding_dir,
            check=True,
        )

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

    def _extract(self, layout: GameLayout, product_id: str) -> None:
        installer_exe = find_installer_exe(layout.installer)
        subprocess.run(["innoextract", "-d", str(layout.game), str(installer_exe)], check=True)

    def _post_extract(self, layout: GameLayout) -> None:
        if self.merge_save:
            merge_support_save_data(layout)
        create_missing_mount_dirs(layout)

    def _write_metadata(self, layout: GameLayout, product_id: str, *, refresh: bool) -> None:
        """metadata.json records the dependency/classification info plus the
        launch profiles parsed from the extracted goggame-*.info."""
        try:
            metadata = get_metadata(layout.name, product_id, refresh=refresh)
        except FETCH_ERRORS as exc:
            print(f"Could not fetch metadata for {layout.name}: {exc}")
            return
        profiles = parse_profiles(layout.game)
        metadata_file = GameMetadataFile(gog=metadata.model_copy(update={"profiles": profiles}))
        layout.metadata_json.write_text(metadata_file.model_dump_json(indent=2))

    def _rm_staging(self, layout: GameLayout) -> None:
        layout.rm_installer()
