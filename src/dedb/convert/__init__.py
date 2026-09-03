"""The DOSBox -> DOSEMU2 config conversion engine.

A standalone library (no dependency on the rest of dedb): parse a
``dosbox.conf`` or a `dosbox` command line, translate it through the
``DosboxConfig`` -> ``DosemuConfig`` anti-corruption layer, apply the
autoexec shims, and write ``dosemu.conf`` + ``userhook.bat``.

The apps (``dedb.dosbox`` / ``dedb.dosemu`` / ``dedb.gog`` /
``dedb.archive``) import everything conversion-related from here and
never reach into the submodules.

    parser      parse_dosbox_conf / parse_dosbox_confs (a .conf -> parsed pair)
    cmdline     parse_dosbox_argv (a `dosbox` argv -> the same pair)
    tokens      split_command (tokenise a DOS command string)
    models      DosboxConfig -> DosemuConfigFromDosbox -> DosemuConfig / dosbox_to_dosemu
    mounts      resolve_mounts / MountPoint (the MOUNT targets in an autoexec)
    autoexec    the shims + autoexec_as_userhook / diagnose_autoexec
    converter   build / build_from_parsed / build_from_argv / write_outputs / convert
    issues      render_issues (the `--issues` text block)
    fieldmap    the ARCHITECTURE.md field-map generator (python -m dedb.convert.fieldmap)
"""

from .autoexec import (
    SHIMS,
    AutoexecIssue,
    Severity,
    autoexec_as_userhook,
    autoexec_line_to_userhook_line,
    diagnose_autoexec,
)
from .cmdline import (
    DosboxCommandLine,
    build_from_argv,
    parse_dosbox_argv,
    parse_dosbox_command_line,
)
from .converter import build, build_from_parsed, convert, write_outputs
from .issues import render_issues
from .models import (
    DosboxConfig,
    DosemuConfig,
    DosemuConfigFromDosbox,
    dosbox_to_dosemu,
)
from .mounts import MountPoint, resolve_mounts
from .parser import parse_dosbox_conf, parse_dosbox_confs
from .tokens import split_command

__all__ = [
    "SHIMS",
    "AutoexecIssue",
    "DosboxCommandLine",
    "DosboxConfig",
    "DosemuConfig",
    "DosemuConfigFromDosbox",
    "MountPoint",
    "Severity",
    "autoexec_as_userhook",
    "autoexec_line_to_userhook_line",
    "build",
    "build_from_argv",
    "build_from_parsed",
    "convert",
    "diagnose_autoexec",
    "dosbox_to_dosemu",
    "parse_dosbox_argv",
    "parse_dosbox_command_line",
    "parse_dosbox_conf",
    "parse_dosbox_confs",
    "render_issues",
    "resolve_mounts",
    "split_command",
    "write_outputs",
]
