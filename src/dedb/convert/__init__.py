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
    models      DosboxConfig / DosemuConfig / dosbox_to_dosemu / TRANSLATIONS
    autoexec    the shims + autoexec_shims / diagnose_autoexec
    converter   build / build_from_parsed / build_from_argv / write_outputs / convert
    fieldmap    the ARCHITECTURE.md field-map generator (python -m dedb.convert.fieldmap)
"""

from .autoexec import (
    SEVERITY_BLURB,
    SEVERITY_HEADING,
    SEVERITY_ORDER,
    AutoexecIssue,
    ResolvedMount,
    Severity,
    Workaround,
    active_workarounds,
    autoexec_shims,
    choice_shim,
    diagnose_autoexec,
    mount_lredir_shim,
    resolve_mounts,
    split_command,
    unsupported_command,
    unsupported_mount_option,
)
from .cmdline import (
    DosboxCommandLine,
    build_from_argv,
    parse_dosbox_argv,
    parse_dosbox_command_line,
)
from .converter import build, build_from_parsed, convert, write_outputs
from .models import (
    TRANSLATIONS,
    UNTRANSLATED_DOSBOX_FIELDS,
    DosboxConfig,
    DosemuConfig,
    Translation,
    dosbox_to_dosemu,
)
from .parser import parse_dosbox_conf, parse_dosbox_confs

__all__ = [
    "SEVERITY_BLURB",
    "SEVERITY_HEADING",
    "SEVERITY_ORDER",
    "TRANSLATIONS",
    "UNTRANSLATED_DOSBOX_FIELDS",
    "AutoexecIssue",
    "DosboxCommandLine",
    "DosboxConfig",
    "DosemuConfig",
    "ResolvedMount",
    "Severity",
    "Translation",
    "Workaround",
    "active_workarounds",
    "autoexec_shims",
    "build",
    "build_from_argv",
    "build_from_parsed",
    "choice_shim",
    "convert",
    "diagnose_autoexec",
    "dosbox_to_dosemu",
    "mount_lredir_shim",
    "parse_dosbox_argv",
    "parse_dosbox_command_line",
    "parse_dosbox_conf",
    "parse_dosbox_confs",
    "resolve_mounts",
    "split_command",
    "unsupported_command",
    "unsupported_mount_option",
    "write_outputs",
]
