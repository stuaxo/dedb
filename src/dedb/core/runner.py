"""Emulator-launch building blocks shared by every backend's runner.

`dedb.gog.runner` and `dedb.archive.runner` differ only in how they build
the DOSBox command line (a GOG game has -conf files and launch profiles;
an archive.org item has a synthetic -c autoexec). Resolving the DOSBox
binary and the actual subprocess/verbose/"not installed" handling are the
same for both, and live here.
"""

import shutil

import click

# Logical [dosbox] dosbox= choice -> actual binary name on PATH. Only
# "dosbox" and "dosbox_staging" are tested; "dosbox_x" and "dosbox_pure"
# are included for people who want to try them.
DOSBOX_BINARIES = {
    "dosbox": "dosbox",
    "dosbox_staging": "dosbox-staging",
    "dosbox_x": "dosbox-x",
    "dosbox_pure": "dosbox-pure",
}

# "default" tries these, in order, and uses the first one installed.
_DEFAULT_PROBE_ORDER = ["dosbox_staging", "dosbox"]


def resolve_dosbox_binary(choice: str) -> str:
    """Map a [dosbox] dosbox= setting to the binary to actually run.
    "default" picks the first of dosbox_staging/dosbox found on PATH,
    falling back to plain "dosbox" if neither is, so the eventual
    FileNotFoundError still names the tool people know to install."""
    if choice == "default":
        for name in _DEFAULT_PROBE_ORDER:
            binary = DOSBOX_BINARIES[name]
            if shutil.which(binary):
                return binary
        return DOSBOX_BINARIES["dosbox"]

    if choice not in DOSBOX_BINARIES:
        valid = ", ".join(["default", *DOSBOX_BINARIES])
        raise click.ClickException(f'Unknown [dosbox] dosbox = "{choice}". Valid options: {valid}')
    return DOSBOX_BINARIES[choice]
