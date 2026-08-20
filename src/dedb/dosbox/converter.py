"""Orchestration logic gluing the parser and models together."""

from pathlib import Path
from typing import Sequence

import click

from .models import DosboxConfigToDosemu, DosemuConfig
from .parser import parse_dosbox_confs


def convert(input_files: Sequence[Path], output_dir: Path, force: bool = False) -> None:
    """Convert one or more dosbox.conf files (merged in order, later files
    overriding earlier ones — the same rule DOSBox itself uses for multiple
    -conf files) into a DOSEMU2 config + userhook.bat, written into
    output_dir."""
    if output_dir.exists() and not force:
        raise click.ClickException(
            f"Output directory '{output_dir}' already exists. Use --force to overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_dict, autoexec_commands = parse_dosbox_confs(input_files)

    transformer = DosboxConfigToDosemu.model_validate(raw_dict)
    dumped = transformer.model_dump(by_alias=True)
    target = DosemuConfig.model_validate(dumped)

    dosemu_conf_path = output_dir / "dosemu.conf"
    with dosemu_conf_path.open("w") as f:
        for key, value in target.model_dump().items():
            f.write(f"{key}={value}\n")

    userhook_path = output_dir / "userhook.bat"
    with userhook_path.open("w") as f:
        for command in autoexec_commands:
            f.write(f"{command}\n")
