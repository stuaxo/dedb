"""Select and resolve dosbox conf files by GOG launch profile.

Replaces the old approach of merging every dosbox*.conf found under a
game's install, which breaks for games whose extra confs are alternate,
mutually-exclusive launch modes (single vs. multiplayer client/server -
see doc/gog.md) rather than pieces meant to be merged together.

A profile is "valid" if its playTask actually references at least one
-conf file - this naturally excludes tool tasks (e.g. GOGDOSConfig.exe)
and document/URL tasks, which never do. Games without a usable
goggame-*.info (or with no conf-referencing playTask) fall back to the
old glob-everything behavior, since that's still correct for the common
case of a single dosbox.conf, or a base conf plus a genuine merge-in
variant.
"""

import re
from pathlib import Path

import click

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


def resolve_conf_files(extracted_dir: Path, profile: GogProfile) -> list[Path]:
    """Resolve a profile's recorded conf basenames to actual files under
    extracted_dir. GOG's recorded paths assume its own installed layout;
    these games are only innoextract'd, so confs are located by basename
    search instead."""
    resolved = []
    for basename in profile.conf_files:
        matches = list(extracted_dir.rglob(basename))
        if not matches:
            raise click.ClickException(f"Could not locate conf file '{basename}' under {extracted_dir}")
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
