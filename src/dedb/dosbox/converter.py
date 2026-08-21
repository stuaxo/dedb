"""Orchestration logic gluing the parser and models together."""

from pathlib import Path
from typing import Sequence

import click

from ..shims.autoexec import autoexec_shims
from .models import DosboxConfig, DosemuConfig, dosbox_to_dosemu
from .parser import parse_dosbox_confs


def build(input_files: Sequence[Path], working_dir: Path | None = None) -> tuple[DosemuConfig, list[str]]:
    """Parse and transform one or more dosbox.conf files (merged in order,
    later files overriding earlier ones, the same rule DOSBox uses for
    multiple -conf files) into (dosemu_config, userhook_lines). Same
    content convert() writes to disk, without writing anything.
    userhook_lines has shims already applied (see dedb.shims.autoexec).
    working_dir, if known, lets the mount shim resolve MOUNT's relative
    paths into LREDIR calls; without it MOUNT lines are commented out."""
    raw_dict, autoexec_commands = parse_dosbox_confs(input_files)

    dosbox_config = DosboxConfig.model_validate(raw_dict)
    target = dosbox_to_dosemu(dosbox_config)

    return target, autoexec_shims(autoexec_commands, working_dir)


def convert(
    input_files: Sequence[Path],
    output_dir: Path,
    force: bool = False,
    *,
    dosemu_filename: str = "dosemu.conf",
    userhook_filename: str = "userhook.bat",
    working_dir: Path | None = None,
) -> None:
    """Convert one or more dosbox.conf files into a DOSEMU2 config +
    userhook.bat, written into output_dir. dosemu_filename/userhook_filename
    let a caller write more than one converted pair into the same
    output_dir (e.g. one per GOG launch profile - see dedb.gog.profiles).
    See build() for working_dir."""
    if output_dir.exists() and not force:
        raise click.ClickException(
            f"Output directory '{output_dir}' already exists. Use --force to overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    target, userhook_lines = build(input_files, working_dir)

    dosemu_conf_path = output_dir / dosemu_filename
    dosemu_conf_path.write_text(target.model_dump_dosemurc())

    userhook_path = output_dir / userhook_filename
    # Shims patch commands known to misbehave under DOSEMU2 - real DOSBox
    # (launched via -conf, not through this file) never sees them.
    # cp437 so DOS renders any box-drawing/extended characters (ASCII-art
    # menus etc.) correctly - matches how parser.py reads the source confs.
    with userhook_path.open("w", encoding="cp437") as f:
        for command in userhook_lines:
            f.write(f"{command}\n")
