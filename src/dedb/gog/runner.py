"""Run a GOG game in DOSBox or DOSEMU2, downloading (and, for DOSEMU2,
converting) it first if that hasn't happened yet.
"""

import subprocess
from pathlib import Path
from typing import Sequence

import click

from .client import owned_games
from .downloader import download_and_extract
from .importer import import_gog_game
from .layout import GameLayout
from .profiles import default_profile, get_conf_files, profile_slug, select_profile, valid_profiles


def ensure_downloaded(gamename: str, download_dir: Path, *, keep: bool) -> GameLayout:
    """Download and extract gamename if it isn't already, returning its layout."""
    layout = GameLayout(download_dir, gamename)
    if layout.is_downloaded():
        return layout

    product_id = next((g.product_id for g in owned_games() if g.gamename == gamename), None)
    if product_id is None:
        raise click.ClickException(f"'{gamename}' not found in your GOG library")
    download_and_extract(gamename, product_id, download_dir, keep=keep)
    return layout


def _profile_file_slug(layout: GameLayout, profile: str | None) -> str | None:
    """The GameLayout slug (None = unsuffixed/default) a given --profile
    choice maps to."""
    profiles = valid_profiles(layout.game)
    if not profiles:
        return None
    chosen = select_profile(layout.game, profile) if profile is not None else default_profile(profiles)
    return None if chosen is default_profile(profiles) else profile_slug(chosen)


def ensure_converted(layout: GameLayout, profile: str | None = None) -> Path:
    """Convert layout's requested launch profile to a DOSEMU2 config if
    that hasn't already been done, returning the resulting conf path.
    profile=None picks the default profile."""
    conf_path = layout.dosemu_conf_for(_profile_file_slug(layout, profile))
    if not conf_path.is_file():
        import_gog_game(layout, profile=profile, force=True)
    return conf_path


def run_dosbox(layout: GameLayout, profile: str | None = None, extra_args: Sequence[str] = ()) -> int:
    conf_files = get_conf_files(layout.game, profile)

    # DOSBox resolves relative MOUNT paths against the working directory it
    # was launched from, not the conf file's location - match GOG's own
    # launcher, which cds into the confs' directory first.
    cmd = ["dosbox"]
    for conf in conf_files:
        cmd += ["-conf", str(conf)]
    cmd += extra_args

    try:
        result = subprocess.run(cmd, cwd=conf_files[0].parent)
    except FileNotFoundError:
        raise click.ClickException("'dosbox' not found on PATH - install it first")
    return result.returncode


def run_dosemu(layout: GameLayout, profile: str | None = None, extra_args: Sequence[str] = ()) -> int:
    dosemu_conf = ensure_converted(layout, profile)
    layout.dosemu_local.mkdir(parents=True, exist_ok=True)

    cmd = [
        "dosemu",
        "-f",
        str(dosemu_conf),
        "--Flocal_dir",
        str(layout.dosemu_local),
        "--Fdrive_c",
        str(layout.game),
    ]
    cmd += extra_args

    click.echo("Note: the game is on C: - run its .exe yourself once dosemu2 boots.")
    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        raise click.ClickException("'dosemu' not found on PATH - install the dosemu2 package first")
    return result.returncode
