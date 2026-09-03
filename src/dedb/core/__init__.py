"""The framework every dedb "app" (dosbox, gog, archive, ...) plugs into.

This package is the app-facing surface: everything below is defined in a
submodule and re-exported here, so apps do ``from dedb.core import X``
and never reach into a sibling app or ``settings.json`` directly.

    refs            game-reference spellings + the resolved Target
    settings        the TOML-backed Settings models + get_settings() + ConfigError
    _registry       the bare scheme -> backend dict + @register_backend
    registry        get_apps() / get_backends() - discovery from settings
    backends        BackendBase + resolve() / resolve_game() / complete_target() + GameRefError
    cliargs         is_game_ref / existing_conf / complete_source SOURCES helpers + cli_command
    downloads       the <download_dir> resolve/create ops + delete_download
    layout          LayoutPaths + NotDownloadedError / UnsafePathError
    local           GameDescription / LocalGame / LaunchProfile - the downloaded-program model
    metadata_file   GameMetadataFile - the metadata.json envelope (a persisted GameDescription)
    downloader      the download+extract template + DownloadError
    runner          the emulator-launch helpers
    metadata_cache  MetadataCache
"""

from ._registry import register_backend
from .backends import BackendBase, GameRefError, complete_target, resolve, resolve_game
from .cliargs import USER_FACING_ERRORS, cli_command, complete_source, existing_conf, is_game_ref
from .downloader import Downloader, DownloadError
from .downloads import delete_download, ensure_download_dir, require_download_dir
from .layout import LayoutPaths, NotDownloadedError, UnsafePathError
from .local import LaunchProfile, LocalGame
from .metadata_cache import MetadataCache, OfflineError
from .metadata_file import GameMetadataFile
from .refs import Target, long_target, short_target
from .registry import get_apps, get_backends
from .runner import dosemu_argv, launch, launch_dosemu, render_cmdline
from .settings import (
    CONFIG_DIR,
    SETTINGS_PATH,
    ConfigError,
    Settings,
    get_settings,
    load_settings,
    save_archive_user,
    scheme_config_path,
)

__all__ = [
    "CONFIG_DIR",
    "SETTINGS_PATH",
    "USER_FACING_ERRORS",
    "BackendBase",
    "ConfigError",
    "DownloadError",
    "Downloader",
    "GameMetadataFile",
    "GameRefError",
    "LaunchProfile",
    "LayoutPaths",
    "LocalGame",
    "MetadataCache",
    "NotDownloadedError",
    "OfflineError",
    "Settings",
    "Target",
    "UnsafePathError",
    "cli_command",
    "complete_source",
    "complete_target",
    "delete_download",
    "dosemu_argv",
    "ensure_download_dir",
    "existing_conf",
    "get_apps",
    "get_backends",
    "get_settings",
    "is_game_ref",
    "launch",
    "launch_dosemu",
    "load_settings",
    "long_target",
    "register_backend",
    "render_cmdline",
    "require_download_dir",
    "resolve",
    "resolve_game",
    "save_archive_user",
    "scheme_config_path",
    "short_target",
]
