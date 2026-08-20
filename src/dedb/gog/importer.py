"""Import an already-downloaded GOG game's dosbox launch profile(s) into
DOSEMU2 config(s), reusing dedb.dosbox's own conversion logic rather than
duplicating it.
"""

from pathlib import Path

import click

from ..dosbox.converter import convert as convert_dosbox
from .layout import GameLayout
from .profiles import default_profile, legacy_find_confs, profile_slug, resolve_conf_files, select_profile, valid_profiles


def _dosemu_filename(slug: str | None) -> str:
    return f"dosemu_{slug}.conf" if slug else "dosemu.conf"


def _userhook_filename(slug: str | None) -> str:
    """
    :param slug: GOG game's slug
    """
    return f"userhook_{slug}.bat" if slug else "userhook.bat"


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
    if not layout.is_downloaded():
        raise click.ClickException(
            f"'{layout.gamename}' hasn't been downloaded yet. "
            f"Run `dedb downloadgog --game {layout.gamename}` first."
        )
    output_dir = output_dir or layout.dosemu

    profiles = valid_profiles(layout.game)

    if not profiles:
        if profile is not None:
            raise click.ClickException(f"No launch profiles found for '{layout.gamename}'.")
        conf_files = legacy_find_confs(layout.game)
        if not conf_files:
            raise click.ClickException(f"No dosbox*.conf found under {layout.game}")
        convert_dosbox(conf_files, output_dir, force=force)
        return {"default": conf_files}

    if profile is not None:
        targets = [select_profile(layout.game, profile)]
    else:
        targets = profiles

    if output_dir.exists() and not force:
        raise click.ClickException(f"'{output_dir}' already exists. Use --force to overwrite.")

    default = default_profile(profiles)
    results: dict[str, list[Path]] = {}
    for p in targets:
        slug = None if p is default else profile_slug(p)
        conf_files = resolve_conf_files(layout.game, p)
        convert_dosbox(
            conf_files,
            output_dir,
            force=True,
            dosemu_filename=_dosemu_filename(slug),
            userhook_filename=_userhook_filename(slug),
        )
        results[slug or "default"] = conf_files
    return results
