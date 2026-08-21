"""Core dedb infrastructure: the settings instance, the app registry
built from it, and the shared downloads-root helper every app's cli.py
uses instead of managing its own download_dir setting. Anything that
needs settings or the list of installed apps (cli.py, an app's own cli
module, ...) should go through here rather than loading settings.json
or importing another app's cli module directly.
"""

from collections import OrderedDict
from functools import lru_cache
from importlib import import_module
from pathlib import Path

import click

from .settings import SETTINGS_PATH, Settings, load_settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_apps() -> "OrderedDict[str, list[click.Command]]":
    """Resolve Settings.apps into each app's contributed click commands,
    keyed by short app name (`dedb.dosbox` -> `dosbox`) in settings order."""
    apps: "OrderedDict[str, list[click.Command]]" = OrderedDict()
    for dotted_path in get_settings().apps:
        module = import_module(f"{dotted_path}.cli")
        short_name = dotted_path.rsplit(".", 1)[-1]
        apps[short_name] = module.commands
    return apps


def get_download_dir(app_name: str) -> Path | None:
    """<download_dir>/<app_name>, or None if [download_dir] isn't configured."""
    download_dir = get_settings().download_dir
    if download_dir is None:
        return None
    return download_dir / app_name


def require_download_dir(app_name: str) -> Path:
    """Like get_download_dir, but raises a ClickException instead of
    returning None when [download_dir] isn't configured - for commands
    that can't do anything without it."""
    app_dir = get_download_dir(app_name)
    if app_dir is None:
        raise click.ClickException(
            f"download_dir is not set. Add it to {SETTINGS_PATH}, e.g.:\n"
            '  download_dir = "/path/to/downloads"'
        )
    return app_dir
