"""Run a GOG game in DOSBox or DOSEMU2, downloading (and, for DOSEMU2,
converting) it first if that hasn't happened yet.
"""

from collections.abc import Sequence
from pathlib import Path

from ..core import Target, get_settings, launch, launch_dosemu
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


def dosbox_conf_argv(layout: GogLayout, target: Target) -> tuple[list[str], Path]:
    """The `dosbox` ``-conf`` argv (no binary) and the working directory it
    runs in, for this game/profile. DOSBox resolves relative MOUNT paths
    (typically "MOUNT C ..") against that directory - GOG's recorded
    workingDir, not necessarily where the confs ended up under innoextract
    (see get_working_dir)."""
    argv = [
        token
        for conf in get_conf_files(layout.game, target.profile)
        for token in ("-conf", str(conf))
    ]
    return argv, get_working_dir(layout.game, target.profile)


def dosemu_conf_path(layout: GogLayout, target: Target) -> Path:
    """The dosemu.conf `run --dosemu` uses for this profile - the path only,
    not regenerated (see ensure_converted)."""
    return layout.dosemu_conf_for(_profile_file_slug(layout, target.profile))


def run_dosbox(
    layout: GogLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    binary = get_settings().dosbox.get_dosbox_binary()
    argv, cwd = dosbox_conf_argv(layout, target)
    return launch(
        [binary, *argv, *extra_args],
        cwd=cwd,
        missing_hint=f"'{binary}' not found on PATH - install it first",
        verbose=verbose,
    )


def run_dosemu(
    layout: GogLayout,
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    profile = target.profile
    return launch_dosemu(
        layout,
        dosemu_conf=ensure_converted(layout, profile),
        userhook_src=layout.userhook_for(_profile_file_slug(layout, profile)),
        extra_args=extra_args,
        verbose=verbose,
    )
