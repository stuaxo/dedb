"""Import an already-downloaded GOG game's dosbox launch profile(s) into
DOSEMU2 config(s), reusing the dedb.convert engine rather than
duplicating it.
"""

from pathlib import Path

from ..convert import DosemuConfig
from ..convert import build as build_dosbox
from ..convert import convert as convert_dosbox
from .layout import GogLayout
from .profiles import (
    ProfileError,
    default_profile,
    legacy_find_confs,
    profile_slug,
    resolve_conf_files,
    resolve_working_dir,
    select_profile,
    valid_profiles,
)


def _resolve_targets(layout: GogLayout, profile: str | None) -> list[tuple[str, list[Path], Path]]:
    """Figure out which profile(s) to process: ``[(label, conf_files,
    working_dir), ...]``, label being "default" or a slug. A game with no
    usable goggame-*.info falls back to a single ("default", every
    dosbox*.conf, ...) entry - the same shape, so callers don't special-case
    it. Raises if the game isn't downloaded, or a requested profile doesn't
    exist."""
    layout.require_downloaded("gog")

    profiles = valid_profiles(layout.game)

    if not profiles:
        if profile is not None:
            raise ProfileError(f"No launch profiles found for '{layout.gamename}'.")
        conf_files = legacy_find_confs(layout.game)
        if not conf_files:
            raise FileNotFoundError(f"No dosbox*.conf found under {layout.game}")
        return [("default", conf_files, conf_files[0].parent)]

    targets = [select_profile(layout.game, profile)] if profile is not None else profiles
    default = default_profile(profiles)
    resolved = []
    for p in targets:
        label = profile_slug(p) if p is not default else "default"
        conf_files = resolve_conf_files(layout.game, p)
        working_dir = resolve_working_dir(layout.game, p) or conf_files[0].parent
        resolved.append((label, conf_files, working_dir))
    return resolved


def import_gog_game(
    layout: GogLayout,
    output_dir: Path | None = None,
    *,
    profile: str | None = None,
    force: bool = False,
) -> dict[str, list[Path]]:
    """Convert layout's DOSBox launch profile(s) into DOSEMU2 config(s)
    under output_dir (defaults to layout.dosemu). With profile=None,
    converts every valid profile: the default profile's pair is written
    unsuffixed (dosemu.conf / userhook.bat), others as
    dosemu_<slug>.conf / userhook_<slug>.bat. profile picks a single
    profile (by name or slug) to convert instead. Returns
    {label: conf_files_used}, label being "default" or a slug.
    """
    output_dir = output_dir or layout.dosemu
    targets = _resolve_targets(layout, profile)

    if output_dir.exists() and not force:
        raise FileExistsError(f"'{output_dir}' already exists. Use --force to overwrite.")

    results: dict[str, list[Path]] = {}
    for label, conf_files, working_dir in targets:
        slug = None if label == "default" else label
        convert_dosbox(
            conf_files,
            output_dir,
            force=True,
            dosemu_filename=layout.dosemu_conf_for(slug).name,
            userhook_filename=layout.userhook_for(slug).name,
            working_dir=working_dir,
        )
        results[label] = conf_files
    return results


def build_gog_game(
    layout: GogLayout, *, profile: str | None = None
) -> dict[str, tuple[list[Path], DosemuConfig, list[str]]]:
    """Like import_gog_game, but only computes the DOSEMU2 config/userhook
    content for each profile in scope, without writing anything to disk.
    Returns {label: (conf_files_used, dosemu_config, userhook_lines)}.
    """
    targets = _resolve_targets(layout, profile)
    results: dict[str, tuple[list[Path], DosemuConfig, list[str]]] = {}
    for label, conf_files, working_dir in targets:
        target, userhook_lines = build_dosbox(conf_files, working_dir)
        results[label] = (conf_files, target, userhook_lines)
    return results
