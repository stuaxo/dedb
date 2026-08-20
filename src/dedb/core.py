"""Core dedb infrastructure: the settings instance and the app registry
built from it. Anything that needs settings or the list of installed apps
(cli.py, an app's own cli module, ...) should go through here rather than
loading settings.json or importing another app's cli module directly.
"""

from collections import OrderedDict
from functools import lru_cache
from importlib import import_module

import click

from .settings import Settings, load_settings


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
