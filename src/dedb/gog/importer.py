"""Import an already-downloaded GOG game's dosbox launch profile(s) into
DOSEMU2 config(s), reusing dedb.dosbox's own conversion logic rather than
duplicating it.
"""

from pathlib import Path

import click

from ..dosbox.converter import build as build_dosbox
from ..dosbox.converter import convert as convert_dosbox
from ..dosbox.models import DosemuConfig
from .layout import GameLayout
from .profiles import (
    default_profile,
    legacy_find_confs,
    profile_slug,
    resolve_conf_files,
    resolve_working_dir,
    select_profile,
    valid_profiles,
)


def _dosemu_filename(slug: str | None) -> str:
    return f"dosemu_{slug}.conf" if slug else "dosemu.conf"


def _userhook_filename(slug: str | None) -> str:
    """
    :param slug: GOG game's slug
    """
    return f"userhook_{slug}.bat" if slug else "userhook.bat"


def _resolve_targets(
    layout: GameLayout, profile: str | None
) -> tuple[bool, list[tuple[str, list[Path], Path]]]:
    """Figure out which profile(s) to process. Returns (is_legacy_fallback,
    [(label, conf_files, working_dir), ...]), label being "default" or a
    slug. Raises if the game isn't downloaded, or a requested profile
    doesn't exist."""
    if not layout.is_downloaded():
        raise click.ClickException(
            f"'{layout.gamename}' hasn't been downloaded yet. "
            f"Run `dedb download gog://{layout.gamename}` first."
        )

    profiles = valid_profiles(layout.game)

    if not profiles:
        if profile is not None:
            raise click.ClickException(f"No launch profiles found for '{layout.gamename}'.")
        conf_files = legacy_find_confs(layout.game)
        if not conf_files:
            raise click.ClickException(f"No dosbox*.conf found under {layout.game}")
        return True, [("default", conf_files, conf_files[0].parent)]

    targets = [select_profile(layout.game, profile)] if profile is not None else profiles
    default = default_profile(profiles)
    resolved = []
    for p in targets:
        label = profile_slug(p) if p is not default else "default"
        conf_files = resolve_conf_files(layout.game, p)
        working_dir = resolve_working_dir(layout.game, p) or conf_files[0].parent
        resolved.append((label, conf_files, working_dir))
    return False, resolved


def import_gog_game(
    layout: GameLayout, output_dir: Path | None = None, *, profile: str | None = None, force: bool = False
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
    is_legacy, targets = _resolve_targets(layout, profile)

    if is_legacy:
        label, conf_files, working_dir = targets[0]
        convert_dosbox(conf_files, output_dir, force=force, working_dir=working_dir)
        return {label: conf_files}

    if output_dir.exists() and not force:
        raise click.ClickException(f"'{output_dir}' already exists. Use --force to overwrite.")

    results: dict[str, list[Path]] = {}
    for label, conf_files, working_dir in targets:
        slug = None if label == "default" else label
        convert_dosbox(
            conf_files,
            output_dir,
            force=True,
            dosemu_filename=_dosemu_filename(slug),
            userhook_filename=_userhook_filename(slug),
            working_dir=working_dir,
        )
        results[label] = conf_files
    return results


def build_gog_game(
    layout: GameLayout, *, profile: str | None = None
) -> dict[str, tuple[list[Path], DosemuConfig, list[str]]]:
    """Like import_gog_game, but only computes the DOSEMU2 config/userhook
    content for each profile in scope, without writing anything to disk.
    Returns {label: (conf_files_used, dosemu_config, userhook_lines)}.
    """
    _is_legacy, targets = _resolve_targets(layout, profile)
    results: dict[str, tuple[list[Path], DosemuConfig, list[str]]] = {}
    for label, conf_files, working_dir in targets:
        target, userhook_lines = build_dosbox(conf_files, working_dir)
        results[label] = (conf_files, target, userhook_lines)
    return results
