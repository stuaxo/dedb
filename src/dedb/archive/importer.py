"""Build a DOSEMU2 config + userhook for a downloaded archive.org item.

archive.org items ship no dosbox.conf - just an ``emulator_start`` path.
emularity launches them by synthesizing a `dosbox` command line (mount C:,
cd, run); ``dosbox_argv`` rebuilds that command line and
``dedb.dosbox.cmdline.build_from_argv`` runs it through the same models a
GOG game's dosbox.conf goes through.
"""

from pathlib import Path

import click

from ..core import GameMetadataFile, long_target
from ..dosbox.cmdline import build_from_argv
from ..dosbox.converter import write_outputs
from ..dosbox.models import DosemuConfig
from .layout import ArchiveLayout
from .models import ArchiveMetadata


def load_metadata(layout: ArchiveLayout) -> ArchiveMetadata:
    if not layout.metadata_json.is_file():
        raise click.ClickException(
            f"No metadata.json for '{layout.identifier}' - run "
            f"`dedb download {long_target('archive', layout.identifier)}` first."
        )
    envelope = GameMetadataFile.read(layout.metadata_json)
    return ArchiveMetadata.model_validate(envelope.source)


def autoexec_commands(emulator_start: str) -> list[str]:
    """The synthetic [autoexec] this item's emulator_start implies."""
    posix_path = emulator_start.replace("\\", "/")
    directory, _sep, name = posix_path.rpartition("/")
    commands = ["MOUNT C .", "C:"]
    if directory:
        commands.append(f"CD {directory.replace('/', chr(92))}")
    commands.append(name)
    return commands


def dosbox_argv(metadata: ArchiveMetadata) -> list[str]:
    """The `dosbox` command line for this item - what emularity synthesizes
    from emulator_start (mount C:, cd, run), as a list of `-c` commands.
    The single source of the archive command line, shared by the importer
    and the runner."""
    argv: list[str] = []
    for command in autoexec_commands(metadata.emulator_start):
        argv += ["-c", command]
    return argv


def build_archive_game(layout: ArchiveLayout) -> tuple[DosemuConfig, list[str]]:
    """Like `import_archive_game` but returns the content instead of writing it."""
    metadata = load_metadata(layout)
    return build_from_argv(dosbox_argv(metadata), working_dir=layout.game)


def import_archive_game(
    layout: ArchiveLayout, output_dir: Path | None = None, *, force: bool = False
) -> None:
    layout.require_downloaded("archive")

    target, userhook_lines = build_archive_game(layout)
    write_outputs(output_dir or layout.dosemu, target, userhook_lines, force=force)
