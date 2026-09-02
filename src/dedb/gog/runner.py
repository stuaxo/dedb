"""Run a GOG game in DOSBox or DOSEMU2, downloading (and, for DOSEMU2,
converting) it first if that hasn't happened yet.
"""

from collections.abc import Sequence
from pathlib import Path

from ..core import Target, get_settings, launch, launch_dosemu, resolve_dosbox_binary
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
    target: Target,
    extra_args: Sequence[str] = (),
    verbose: bool = False,
) -> int:
    profile = target.profile
    binary = resolve_dosbox_binary(get_settings().dosbox.dosbox)

    cmd = [binary]
    for conf in get_conf_files(layout.game, profile):
        cmd += ["-conf", str(conf)]
    cmd += extra_args

    # DOSBox resolves relative MOUNT paths (typically "MOUNT C ..") against
    # the directory it was launched from - GOG's recorded workingDir, not
    # necessarily wherever the confs themselves ended up under innoextract
    # (see get_working_dir).
    return launch(
        cmd,
        cwd=get_working_dir(layout.game, profile),
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
