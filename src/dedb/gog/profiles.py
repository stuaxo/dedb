"""Select and resolve dosbox conf files by GOG launch profile.

A game's extra confs are often alternate, mutually-exclusive launch
modes (single vs. multiplayer client/server - see doc/gog.md), not
pieces meant to be merged. Merging every dosbox*.conf found under the
install breaks those games; this module picks the confs for one profile
instead.

A profile is "valid" if its playTask references at least one -conf file.
This excludes tool tasks (e.g. GOGDOSConfig.exe) and document/URL tasks,
which never do. Games without a usable goggame-*.info, or with no
conf-referencing playTask, fall back to merging every dosbox*.conf found
- still correct for a single conf, or a base conf plus a genuine
merge-in variant.
"""

import re
from pathlib import Path

import click

from ..core import LaunchMode
from .gameinfo import parse_profiles
from .models import GogProfile


def legacy_find_confs(extracted_dir: Path) -> list[Path]:
    """Every dosbox*.conf under extracted_dir, merged in order - the
    fallback for games with no usable goggame-*.info."""
    return sorted(
        path for path in extracted_dir.rglob("*.conf") if path.name.lower().startswith("dosbox")
    )


def valid_profiles(extracted_dir: Path) -> list[GogProfile]:
    return [p for p in parse_profiles(extracted_dir) if p.conf_files]


def default_profile(profiles: list[GogProfile]) -> GogProfile:
    return next((p for p in profiles if p.is_primary), profiles[0])


def profile_slug(profile: GogProfile) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", profile.name.lower()).strip("_")
    return slug or "profile"


def launch_modes(extracted_dir: Path) -> list[LaunchMode]:
    """The game's launch modes for `LocalGame` / `metadata.json` - one per
    valid profile, or a single default mode for a game with no usable
    goggame-*.info. Mirrors the default-profile-is-unsuffixed rule in
    `GogLayout` (see `dosemu_conf_for`)."""
    profiles = valid_profiles(extracted_dir)
    if not profiles:
        return [LaunchMode(slug=None, name="default", is_default=True)]

    default = default_profile(profiles)
    return [
        LaunchMode(
            slug=None if p is default else profile_slug(p),
            name=p.name or profile_slug(p),
            is_default=p is default,
        )
        for p in profiles
    ]


def resolve_conf_files(extracted_dir: Path, profile: GogProfile) -> list[Path]:
    """Resolve a profile's recorded conf basenames to actual files under
    extracted_dir. GOG's recorded paths assume its own installed layout;
    these games are only innoextract'd, so confs are located by basename
    search instead."""
    resolved = []
    for basename in profile.conf_files:
        matches = list(extracted_dir.rglob(basename))
        if not matches:
            raise click.ClickException(
                f"Could not locate conf file '{basename}' under {extracted_dir}"
            )
        resolved.append(matches[0])
    return resolved


def select_profile(extracted_dir: Path, profile_name: str) -> GogProfile:
    """Match profile_name against every valid profile's slug or exact name."""
    profiles = valid_profiles(extracted_dir)
    for p in profiles:
        if profile_name in (p.name, profile_slug(p)):
            return p

    available = ", ".join(profile_slug(p) for p in profiles) or "(none)"
    raise click.ClickException(f"No such profile '{profile_name}'. Available: {available}")


def get_conf_files(extracted_dir: Path, profile_name: str | None) -> list[Path]:
    """The conf files to hand to DOSBox/dosemu for a given profile choice.
    profile_name=None picks the default profile if any valid profile
    exists, else falls back to legacy_find_confs."""
    profiles = valid_profiles(extracted_dir)

    if profile_name is not None:
        return resolve_conf_files(extracted_dir, select_profile(extracted_dir, profile_name))

    if profiles:
        return resolve_conf_files(extracted_dir, default_profile(profiles))

    conf_files = legacy_find_confs(extracted_dir)
    if not conf_files:
        raise click.ClickException(f"No dosbox*.conf found under {extracted_dir}")
    return conf_files


def resolve_working_dir(extracted_dir: Path, profile: GogProfile) -> Path | None:
    """Resolve profile's recorded workingDir (e.g. "DOSBOX") to an actual
    directory under extracted_dir by basename search, the same
    innoextract-layout-mismatch reasoning as resolve_conf_files - or None
    if it wasn't recorded, or can't be found."""
    if not profile.working_dir:
        return None
    basename = profile.working_dir.replace("\\", "/").rsplit("/", 1)[-1]
    matches = [path for path in extracted_dir.rglob(basename) if path.is_dir()]
    return matches[0] if matches else None


def get_working_dir(extracted_dir: Path, profile_name: str | None) -> Path:
    """The directory to launch real DOSBox from for a given profile choice.

    GOG's recorded workingDir (e.g. "DOSBOX") is where dosbox.exe and its
    confs sit together in a real install, so relative MOUNT paths in the
    autoexec (typically "MOUNT C ..") resolve correctly from there. Under
    innoextract, dosbox.exe's directory still matches that recorded name,
    but the confs often don't: they're placed by InnoSetup [Code]-script
    file copies, which innoextract can't execute, so it dumps them under
    __support/ instead. Using the confs' own directory as cwd mounts the
    wrong directory as C:, missing the game files. Resolve the recorded
    workingDir by basename search instead, falling back to the confs'
    directory if that can't be found.
    """
    profiles = valid_profiles(extracted_dir)
    profile = (
        select_profile(extracted_dir, profile_name)
        if profile_name is not None
        else (default_profile(profiles) if profiles else None)
    )

    if profile is not None:
        resolved = resolve_working_dir(extracted_dir, profile)
        if resolved is not None:
            return resolved

    return get_conf_files(extracted_dir, profile_name)[0].parent
