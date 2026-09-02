"""Build a DOSEMU2 config + userhook for a downloaded archive.org item.

archive.org items ship no dosbox.conf - just an ``emulator_start`` path. So
rather than parsing, this uses DOSBox's built-in defaults and synthesizes the
autoexec directly (mount C:, cd, run) - what archive.org's own player does.
"""

from pathlib import Path

import click

from ..core import long_target
from ..dosbox.converter import build as build_dosbox_defaults
from ..dosbox.models import DosemuConfig
from ..shims.autoexec import autoexec_shims
from .layout import ArchiveLayout
from .models import ArchiveMetadata, GameMetadataFile

DOSEMU_CONF_NAME = "dosemu.conf"
USERHOOK_NAME = "userhook.bat"


def load_metadata(layout: ArchiveLayout) -> ArchiveMetadata:
    if not layout.metadata_json.is_file():
        raise click.ClickException(
            f"No metadata.json for '{layout.identifier}' - run "
            f"`dedb download {long_target('archive', layout.identifier)}` first."
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


def build_archive_game(layout: ArchiveLayout) -> tuple[DosemuConfig, list[str]]:
    """Like `import_archive_game` but returns the content instead of writing it."""
    metadata = load_metadata(layout)
    target, _defaults_userhook = build_dosbox_defaults([])
    userhook_lines = autoexec_shims(autoexec_commands(metadata.emulator_start), layout.game)
    return target, userhook_lines


def import_archive_game(
    layout: ArchiveLayout, output_dir: Path | None = None, *, force: bool = False
) -> None:
    if not layout.is_downloaded():
        raise click.ClickException(
            f"'{layout.identifier}' hasn't been downloaded yet. Run "
            f"`dedb download {long_target('archive', layout.identifier)}` first."
        )

    output_dir = output_dir or layout.dosemu
    if output_dir.exists() and not force:
        raise click.ClickException(f"'{output_dir}' already exists. Use --force to overwrite.")
    output_dir.mkdir(parents=True, exist_ok=True)

    target, userhook_lines = build_archive_game(layout)

    (output_dir / DOSEMU_CONF_NAME).write_text(target.model_dump_dosemurc())

    # cp437 so DOS renders extended characters - matches dedb.dosbox.converter.
    with (output_dir / USERHOOK_NAME).open("w", encoding="cp437") as f:
        for command in userhook_lines:
            f.write(f"{command}\n")
