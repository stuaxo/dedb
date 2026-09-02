"""Shared dedb settings, backed by a small TOML file under the user's XDG
config directory. Any app (dosbox, gog, ...) can read from here; app-specific
caches live in their own subdirectory of CONFIG_DIR rather than in here.

load_settings() never raises: a missing file is created from the packaged
default (dedbconf.default.toml), and an unreadable or invalid file falls
back to the built-in defaults with a warning. dedb should always start.
"""

import json
import os
import sys
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, field_validator

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "dedb"


CONFIG_DIR = _config_dir()
SETTINGS_PATH = CONFIG_DIR / "dedbconf.toml"
DEFAULT_SETTINGS_RESOURCE = "dedbconf.default.toml"


class DosboxSettings(BaseModel):
    # Which real DOSBox binary `dedb run <target> --dosbox` launches. "default" picks
    # the first installed of dosbox_staging or dosbox. Other recognized
    # values: "dosbox", "dosbox_staging", "dosbox_x", "dosbox_pure" - only
    # "dosbox" and "dosbox_staging" have actually been tested so far. See
    # dedb.gog.runner.resolve_dosbox_binary.
    dosbox: str = "default"


class ArchiveSettings(BaseModel):
    # archive.org screen name whose public favorites `lsarchive` lists.
    # When unset, `lsarchive` prompts for it and offers to save it here.
    favorites_user: str | None = None


class Settings(BaseModel):
    # dotted module paths, each expected to expose a `cli.commands` list -
    # mirrors Django's INSTALLED_APPS.
    apps: list[str] = [
        "dedb.dosbox",
        "dedb.gog",
        "dedb.archive",
    ]
    # Shared downloads root - each app gets its own namespaced subdirectory
    # under it (<download_dir>/gog/, <download_dir>/archive/, ...), resolved
    # by dedb.core.require_download_dir/get_download_dir.
    download_dir: Path | None = None
    dosbox: DosboxSettings = DosboxSettings()
    archive: ArchiveSettings = ArchiveSettings()

    @field_validator("download_dir", mode="before")
    @classmethod
    def _expand_download_dir(cls, value: object) -> object:
        """Expand a leading ~ and any $VARs in download_dir, so
        `download_dir = "~/downloads"` resolves against $HOME rather than
        becoming a literal `~` directory under the working dir."""
        if isinstance(value, str):
            return os.path.expanduser(os.path.expandvars(value))
        return value


def default_settings_text() -> str:
    """The packaged default config, comments and all."""
    return (files("dedb") / DEFAULT_SETTINGS_RESOURCE).read_text(encoding="utf-8")


def _write_default_settings() -> None:
    """Populate SETTINGS_PATH from the packaged default on first run. Best
    effort - a config dir we can't write to just means we run on the
    built-in defaults this time."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(default_settings_text(), encoding="utf-8")
    except OSError as exc:
        print(f"dedb: could not create {SETTINGS_PATH}: {exc}", file=sys.stderr)


def load_settings() -> Settings:
    """Load settings, never raising. Creates the file from the packaged
    default when it's missing; on a parse or validation error, warns and
    returns the built-in defaults."""
    if not SETTINGS_PATH.is_file():
        _write_default_settings()

    if not SETTINGS_PATH.is_file():
        return Settings()

    try:
        with SETTINGS_PATH.open("rb") as f:
            data = tomllib.load(f)
        return Settings.model_validate(data)
    except (OSError, ValueError) as exc:
        # ValueError covers both tomllib.TOMLDecodeError and pydantic's
        # ValidationError.
        print(f"dedb: ignoring invalid {SETTINGS_PATH} ({exc}); using defaults", file=sys.stderr)
        return Settings()


def save_archive_favorites_user(username: str) -> None:
    """Write ``favorites_user`` into the ``[archive]`` section of the
    on-disk config, preserving its comments and creating the file or the
    section as needed. Raises OSError if the file can't be written."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.is_file():
        _write_default_settings()

    lines = (
        SETTINGS_PATH.read_text(encoding="utf-8").splitlines() if SETTINGS_PATH.is_file() else []
    )
    # json.dumps yields a double-quoted string with the same escaping a
    # TOML basic string uses for the characters that can appear here.
    new_line = f"favorites_user = {json.dumps(username)}"

    in_archive = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_archive = stripped == "[archive]"
            continue
        if in_archive and stripped.split("=", 1)[0].strip() == "favorites_user":
            lines[i] = new_line
            break
    else:
        if "[archive]" in (s.strip() for s in lines):
            idx = next(i for i, s in enumerate(lines) if s.strip() == "[archive]")
            lines.insert(idx + 1, new_line)
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines += ["[archive]", new_line]

    SETTINGS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
