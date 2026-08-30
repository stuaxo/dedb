"""Shared dedb settings, backed by a small TOML file under the user's XDG
config directory. Any app (dosbox, gog, ...) can read from here; app-specific
caches live in their own subdirectory of CONFIG_DIR rather than in here."""

import os
import sys
from pathlib import Path

from pydantic import BaseModel

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


class GogSettings(BaseModel):
    # Optional: restrict `downloadgog` to exactly these game ids. Without
    # this, it downloads every owned game classified as DOSBox-based - see
    # dedb.gog.classify.
    curated_games: list[str] = []


class DosboxSettings(BaseModel):
    # Which real DOSBox binary `dedb run <target> --dosbox` launches. "default" picks
    # the first installed of dosbox_staging or dosbox. Other recognized
    # values: "dosbox", "dosbox_staging", "dosbox_x", "dosbox_pure" - only
    # "dosbox" and "dosbox_staging" have actually been tested so far. See
    # dedb.gog.runner.resolve_dosbox_binary.
    dosbox: str = "default"


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
    gog: GogSettings = GogSettings()
    dosbox: DosboxSettings = DosboxSettings()


def load_settings() -> Settings:
    if not SETTINGS_PATH.is_file():
        return Settings()

    with SETTINGS_PATH.open("rb") as f:
        data = tomllib.load(f)
    return Settings.model_validate(data)
