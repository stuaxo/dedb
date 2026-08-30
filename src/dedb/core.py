"""Core dedb infrastructure: the settings instance, the app registry
built from it, and the shared downloads-root helper every app's cli.py
uses instead of managing its own download_dir setting. Anything that
needs settings or the list of installed apps (cli.py, an app's own cli
module, ...) should go through here rather than loading settings.json
or importing another app's cli module directly.
"""

import shutil
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


def get_backends() -> "OrderedDict[str, object]":
    """Import each app's optional `backend` module (which self-registers via
    dedb.backends.register_backend) and return the registry, keyed by scheme
    (== app short name) in Settings.apps order. Apps without a backend module
    (e.g. dedb.dosbox) are skipped."""
    from .backends import _REGISTRY

    for dotted_path in get_settings().apps:
        try:
            import_module(f"{dotted_path}.backend")
        except ModuleNotFoundError as exc:
            # Only swallow "there is no such backend module"; a genuine
            # broken import *inside* an existing backend module must surface.
            if exc.name != f"{dotted_path}.backend":
                raise

    backends: "OrderedDict[str, object]" = OrderedDict()
    for dotted_path in get_settings().apps:
        short_name = dotted_path.rsplit(".", 1)[-1]
        if short_name in _REGISTRY:
            backends[short_name] = _REGISTRY[short_name]
    return backends


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


def remove_download(download_root: Path, name: str, *, assume_yes: bool) -> None:
    """Shared implementation of the `rm*` commands: delete one game/item's
    whole directory tree (game files, converted config, cached
    metadata.json, ...) under an app's downloads root, after confirming.
    Refuses anything that doesn't resolve to a single child of the root."""
    root = download_root.resolve()
    target = (download_root / name).resolve()
    if target.parent != root:
        raise click.ClickException(f"Refusing to remove '{name}' - not a single item under {download_root}")

    if not target.exists():
        click.echo(f"Nothing to remove for '{name}' ({target} doesn't exist)")
        return
    if not assume_yes:
        click.confirm(f"Remove '{name}' and everything under {target}?", abort=True)
    shutil.rmtree(target)
    click.echo(f"Removed '{name}' ({target})")
