"""Build a DOSEMU2 config + userhook for an already-downloaded
archive.org item.

Unlike GOG games, archive.org items ship no dosbox.conf at all - just an
"emulator_start" path (see dedb.archive.client), relative to the
extracted archive's root, and nothing else. There's nothing to parse,
so instead of reusing dedb.dosbox.converter's conf-parsing path, this
takes DOSBox's own defaults (dedb.dosbox.converter.build with no input
files) and synthesizes the userhook.bat's autoexec directly: mount the
game root as C:, cd to emulator_start's directory (if any), then run it
- the same minimal autoexec archive.org's own in-browser DOSBox player
runs for a plain "emulator": "dosbox" item.
"""

from pathlib import Path

import click

from ..dosbox.converter import build as build_dosbox_defaults
from ..dosbox.models import DosemuConfig
from ..shims.autoexec import autoexec_shims
from .layout import GameLayout
from .models import ArchiveMetadata, GameMetadataFile

DOSEMU_CONF_NAME = "dosemu.conf"
USERHOOK_NAME = "userhook.bat"


def load_metadata(layout: GameLayout) -> ArchiveMetadata:
    if not layout.metadata_json.is_file():
        raise click.ClickException(
            f"No metadata.json for '{layout.identifier}' - run `dedb download archive://{layout.identifier}` first."
        )
    return GameMetadataFile.model_validate_json(layout.metadata_json.read_text()).archive


def autoexec_commands(emulator_start: str) -> list[str]:
    """The synthetic [autoexec] this item's emulator_start implies."""
    posix_path = emulator_start.replace("\\", "/")
    directory, _sep, name = posix_path.rpartition("/")
    commands = ["MOUNT C .", "C:"]
    if directory:
        commands.append(f"CD {directory.replace('/', chr(92))}")
    commands.append(name)
    return commands


def build_archive_game(layout: GameLayout) -> tuple[DosemuConfig, list[str]]:
    """Like import_archive_game, but only computes the DOSEMU2
    config/userhook content, without writing anything to disk."""
    metadata = load_metadata(layout)
    target, _defaults_userhook = build_dosbox_defaults([])
    userhook_lines = autoexec_shims(autoexec_commands(metadata.emulator_start), layout.game)
    return target, userhook_lines


def import_archive_game(layout: GameLayout, output_dir: Path | None = None, *, force: bool = False) -> None:
    if not layout.is_downloaded():
        raise click.ClickException(
            f"'{layout.identifier}' hasn't been downloaded yet. Run `dedb download archive://{layout.identifier}` first."
        )

    output_dir = output_dir or layout.dosemu
    if output_dir.exists() and not force:
        raise click.ClickException(f"'{output_dir}' already exists. Use --force to overwrite.")
    output_dir.mkdir(parents=True, exist_ok=True)

    target, userhook_lines = build_archive_game(layout)

    (output_dir / DOSEMU_CONF_NAME).write_text(target.model_dump_dosemurc())

    # cp437 so DOS renders any box-drawing/extended characters correctly -
    # matches dedb.dosbox.converter.convert.
    with (output_dir / USERHOOK_NAME).open("w", encoding="cp437") as f:
        for command in userhook_lines:
            f.write(f"{command}\n")
