"""The framework every dedb "app" (dosbox, gog, archive, ...) plugs into.

This package is the app-facing surface: everything below is defined in a
submodule and re-exported here, so apps do ``from dedb.core import X``
and never reach into a sibling app or ``settings.json`` directly.

    refs            game-reference spellings + the resolved Target
    settings        the TOML-backed Settings models + get_settings()
    _registry       the bare scheme -> backend dict + @register_backend
    registry        get_apps() / get_backends() - discovery from settings
    backends        BackendBase + resolve() / resolve_game()
    downloads       the <download_dir> resolve/create ops + `dedb rm`
    layout          LayoutPaths - the per-download directory tree
    local           LocalGame / LaunchMode - the downloaded-program model
    metadata_file   GameMetadataFile - the metadata.json envelope
    downloader      the download+extract template
    runner          the emulator-launch helpers
    metadata_cache  MetadataCache
"""

from ._registry import register_backend
from .backends import BackendBase, resolve, resolve_game
from .downloader import Downloader
from .downloads import ensure_download_dir, remove_download, require_download_dir
from .layout import LayoutPaths
from .local import LaunchMode, LocalGame
from .metadata_cache import MetadataCache, OfflineError
from .metadata_file import GameMetadataFile
from .refs import Target, long_target, short_target
from .registry import get_apps, get_backends
from .runner import launch, launch_dosemu
from .settings import (
    CONFIG_DIR,
    SETTINGS_PATH,
    Settings,
    get_settings,
    load_settings,
    save_archive_favorites_user,
    scheme_config_path,
)

__all__ = [
    "CONFIG_DIR",
    "SETTINGS_PATH",
    "BackendBase",
    "Downloader",
    "GameMetadataFile",
    "LaunchMode",
    "LayoutPaths",
    "LocalGame",
    "MetadataCache",
    "OfflineError",
    "Settings",
    "Target",
    "ensure_download_dir",
    "get_apps",
    "get_backends",
    "get_settings",
    "launch",
    "launch_dosemu",
    "load_settings",
    "long_target",
    "register_backend",
    "remove_download",
    "require_download_dir",
    "resolve",
    "resolve_game",
    "save_archive_favorites_user",
    "scheme_config_path",
    "short_target",
]
