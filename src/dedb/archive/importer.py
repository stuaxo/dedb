"""Build a DOSEMU2 config + userhook for a downloaded archive.org item.

archive.org items ship no dosbox.conf - just an ``emulator_start`` path. So
rather than parsing, this uses DOSBox's built-in defaults and synthesizes the
autoexec directly (mount C:, cd, run) - what archive.org's own player does.
"""

from pathlib import Path

import click

from ..core import long_target
from ..dosbox.converter import build as build_dosbox_defaults
from ..dosbox.converter import write_outputs
from ..dosbox.models import DosemuConfig
from ..shims.autoexec import autoexec_shims
from .layout import ArchiveLayout
from .models import ArchiveMetadata, GameMetadataFile


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

    target, userhook_lines = build_archive_game(layout)
    write_outputs(output_dir or layout.dosemu, target, userhook_lines, force=force)
