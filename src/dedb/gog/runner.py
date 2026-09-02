"""Run a GOG game in DOSBox or DOSEMU2, downloading (and, for DOSEMU2,
converting) it first if that hasn't happened yet.
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from ..core import get_settings
from .client import owned_games
from .downloader import download_and_extract
from .importer import import_gog_game
from .layout import GameLayout
from .profiles import (
    default_profile,
    get_conf_files,
    get_working_dir,
    profile_slug,
    select_profile,
    valid_profiles,
)

# Logical [dosbox] dosbox= choice -> actual binary name on PATH. Only
# "dosbox" and "dosbox_staging" are tested; "dosbox_x" and "dosbox_pure"
# are included for people who want to try them.
DOSBOX_BINARIES = {
    "dosbox": "dosbox",
    "dosbox_staging": "dosbox-staging",
    "dosbox_x": "dosbox-x",
    "dosbox_pure": "dosbox-pure",
}

# "default" tries these, in order, and uses the first one installed.
_DEFAULT_PROBE_ORDER = ["dosbox_staging", "dosbox"]


def resolve_dosbox_binary(choice: str) -> str:
    """Map a [dosbox] dosbox= setting to the binary to actually run.
    "default" picks the first of dosbox_staging/dosbox found on PATH,
    falling back to plain "dosbox" if neither is, so the eventual
    FileNotFoundError still names the tool people know to install."""
    if choice == "default":
        for name in _DEFAULT_PROBE_ORDER:
            binary = DOSBOX_BINARIES[name]
            if shutil.which(binary):
                return binary
        return DOSBOX_BINARIES["dosbox"]

    if choice not in DOSBOX_BINARIES:
        valid = ", ".join(["default", *DOSBOX_BINARIES])
        raise click.ClickException(f'Unknown [dosbox] dosbox = "{choice}". Valid options: {valid}')
    return DOSBOX_BINARIES[choice]


def ensure_downloaded(
    gamename: str,
    download_dir: Path,
    *,
    keep: bool,
    refresh_metadata: bool = False,
    redownload: bool = False,
) -> GameLayout:
    """Download and extract gamename if it isn't already, returning its layout.
    --redownload re-fetches it even when already present; --refreshmetadata
    re-fetches the cached GOG dependency metadata."""
    layout = GameLayout(download_dir, gamename)
    if not (redownload or refresh_metadata or not layout.is_downloaded()):
        return layout

    product_id = next((g.product_id for g in owned_games() if g.gamename == gamename), None)
    if product_id is None:
        raise click.ClickException(f"'{gamename}' not found in your GOG library")
    download_and_extract(
        gamename,
        product_id,
        download_dir,
        keep=keep,
        refresh=refresh_metadata,
        redownload=redownload,
    )
    return layout


def _profile_file_slug(layout: GameLayout, profile: str | None) -> str | None:
    """The GameLayout slug (None = unsuffixed/default) a given --profile
    choice maps to."""
    profiles = valid_profiles(layout.game)
    if not profiles:
        return None
    chosen = (
        select_profile(layout.game, profile) if profile is not None else default_profile(profiles)
    )
    return None if chosen is default_profile(profiles) else profile_slug(chosen)


def ensure_converted(layout: GameLayout, profile: str | None = None) -> Path:
    """(Re)generate layout's DOSEMU2 config(s) for the requested launch
    profile, returning the resulting conf path. profile=None picks the
    default profile. Runs on every launch - the conversion is
    deterministic and cheap, and doing it each time keeps the config in
    step with the installed dedb instead of lingering from whatever
    version first downloaded the game."""
    import_gog_game(layout, profile=profile, force=True)
    return layout.dosemu_conf_for(_profile_file_slug(layout, profile))


def run_dosbox(
    layout: GameLayout,
    profile: str | None = None,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    conf_files = get_conf_files(layout.game, profile)
    binary = resolve_dosbox_binary(get_settings().dosbox.dosbox)

    # DOSBox resolves relative MOUNT paths (typically "MOUNT C ..") against
    # the directory it was launched from - GOG's recorded workingDir, not
    # necessarily wherever the confs themselves ended up under innoextract
    # (see get_working_dir).
    cmd = [binary]
    for conf in conf_files:
        cmd += ["-conf", str(conf)]
    cmd += extra_args

    cwd = get_working_dir(layout.game, profile)
    if verbose:
        click.echo(f"$ cd {shlex.quote(str(cwd))} && {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=cwd)
    except FileNotFoundError:
        raise click.ClickException(f"'{binary}' not found on PATH - install it first") from None
    return result.returncode


def run_dosemu(
    layout: GameLayout,
    profile: str | None = None,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    dosemu_conf = ensure_converted(layout, profile)
    layout.dosemu_local.mkdir(parents=True, exist_ok=True)

    # DOSEMU2's boot chain (dosrc.d/4uhook.bat) auto-runs only
    # %USERDRV%:\userhook.bat. --Fdrive_c maps C: to layout.game, so that
    # means layout.game/userhook.bat, not anything under layout.dosemu.
    # Stage the selected profile's generated userhook.bat there before
    # every launch, since the active profile can change between runs.
    userhook_src = layout.userhook_for(_profile_file_slug(layout, profile))
    shutil.copyfile(userhook_src, layout.game / "userhook.bat")

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
        # userhook.bat's LREDIR calls (see
        # dedb.shims.autoexec.mount_lredir_shim) only ever target paths
        # under the game's own directory - permit exactly that, nothing
        # wider.
        "-I",
        f'$_lredir_paths = "{layout.game}"',
    ]
    cmd += extra_args

    if verbose:
        click.echo(f"$ {shlex.join(cmd)}")

    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        raise click.ClickException(
            "'dosemu' not found on PATH - install the dosemu2 package first"
        ) from None
    return result.returncode
