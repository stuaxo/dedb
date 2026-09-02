"""Run a GOG game in DOSBox or DOSEMU2, downloading (and, for DOSEMU2,
converting) it first if that hasn't happened yet.
"""

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from ..core import get_settings, resolve_dosbox_binary
from .importer import import_gog_game
from .layout import GogLayout
from .profiles import (
    default_profile,
    get_conf_files,
    get_working_dir,
    profile_slug,
    select_profile,
    valid_profiles,
)


def _profile_file_slug(layout: GogLayout, profile: str | None) -> str | None:
    """The GogLayout slug (None = unsuffixed/default) a given --profile
    choice maps to."""
    profiles = valid_profiles(layout.game)
    if not profiles:
        return None
    chosen = (
        select_profile(layout.game, profile) if profile is not None else default_profile(profiles)
    )
    return None if chosen is default_profile(profiles) else profile_slug(chosen)


def ensure_converted(layout: GogLayout, profile: str | None = None) -> Path:
    """(Re)generate layout's DOSEMU2 config(s) for the requested launch
    profile, returning the resulting conf path. profile=None picks the
    default profile. Runs on every launch - the conversion is
    deterministic and cheap, and doing it each time keeps the config in
    step with the installed dedb instead of lingering from whatever
    version first downloaded the game."""
    import_gog_game(layout, profile=profile, force=True)
    return layout.dosemu_conf_for(_profile_file_slug(layout, profile))


def run_dosbox(
    layout: GogLayout,
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
    layout: GogLayout,
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
