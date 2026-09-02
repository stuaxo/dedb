"""The framework every dedb "app" (dosbox, gog, archive, ...) plugs into:
settings, the app/backend registry built from them, the download-root
helpers, plus the `BackendBase` contract and the `Target` / layout /
metadata-cache building blocks (re-exported here from submodules).

Apps import from `dedb.core`, never from each other or `settings.json`.
"""

import shutil
import tempfile
from collections import OrderedDict
from functools import lru_cache
from importlib import import_module
from pathlib import Path

import click

from .backends import (
    BackendBase,
    Target,
    long_target,
    register_backend,
    resolve,
    short_target,
)
from .layout import LayoutPaths
from .metadata_cache import JsonMetadataCache, OfflineError
from .settings import (
    CONFIG_DIR,
    SETTINGS_PATH,
    Settings,
    load_settings,
    save_archive_favorites_user,
)

__all__ = [
    "CONFIG_DIR",
    "SETTINGS_PATH",
    "BackendBase",
    "JsonMetadataCache",
    "LayoutPaths",
    "OfflineError",
    "Settings",
    "Target",
    "ensure_download_dir",
    "get_apps",
    "get_backends",
    "get_download_dir",
    "get_settings",
    "load_settings",
    "long_target",
    "register_backend",
    "remove_download",
    "require_download_dir",
    "resolve",
    "save_archive_favorites_user",
    "short_target",
]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_apps() -> "OrderedDict[str, list[click.Command]]":
    """Resolve Settings.apps into each app's contributed click commands,
    keyed by short app name (`dedb.dosbox` -> `dosbox`) in settings order."""
    apps: OrderedDict[str, list[click.Command]] = OrderedDict()
    for dotted_path in get_settings().apps:
        module = import_module(f"{dotted_path}.cli")
        short_name = dotted_path.rsplit(".", 1)[-1]
        apps[short_name] = module.commands
    return apps


def get_backends() -> "OrderedDict[str, object]":
    """Import each app's optional `backend` module (which self-registers via
    dedb.core.register_backend) and return the registry, keyed by scheme
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

    backends: OrderedDict[str, object] = OrderedDict()
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
    that can't do anything without it. Doesn't check the directory
    exists; the download path uses ensure_download_dir for that."""
    app_dir = get_download_dir(app_name)
    if app_dir is None:
        raise click.ClickException(
            f"download_dir is not set. Add it to {SETTINGS_PATH}, e.g.:\n"
            '  download_dir = "/path/to/downloads"'
        )
    return app_dir


def ensure_download_dir(app_name: str) -> Path:
    """require_download_dir, plus make sure the app's downloads dir exists
    ready to write into. The per-app subdir is created whenever its parent
    - the configured download_dir - is already there. A missing
    download_dir itself is created only when it sits under the system temp
    dir, a throwaway location; anywhere else a typo in the setting should
    surface as an error rather than scatter empty trees across the disk."""
    app_dir = require_download_dir(app_name)
    if app_dir.is_dir():
        return app_dir

    configured = app_dir.parent  # == settings.download_dir
    if configured.is_dir():
        app_dir.mkdir(exist_ok=True)
        return app_dir

    tmp_root = Path(tempfile.gettempdir()).resolve()
    resolved = app_dir.resolve()
    if resolved == tmp_root or tmp_root in resolved.parents:
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir

    raise click.ClickException(
        f"download_dir '{configured}' does not exist. Create it first "
        f"(it's auto-created only under {tmp_root})."
    )


# A resolved download root with fewer parts than this - '/', '/home', a
# bare drive - is almost certainly a misconfigured download_dir, not
# somewhere we should be running rmtree beneath.
_MIN_SAFE_ROOT_PARTS = 3


def remove_download(download_root: Path, name: str, *, assume_yes: bool) -> None:
    """Delete one downloaded game/item's directory tree, after confirming.

    Refuses anything that doesn't resolve to a single child of the root.
    """
    root = download_root.resolve()
    if len(root.parts) < _MIN_SAFE_ROOT_PARTS:
        raise click.ClickException(
            f"Refusing to touch '{root}' - download_dir looks misconfigured."
        )

    target = (download_root / name).resolve()
    if target.parent != root:
        raise click.ClickException(
            f"Refusing to remove '{name}' - not a single item under {download_root}"
        )

    if not target.exists():
        click.echo(f"Nothing to remove for '{name}' ({target} doesn't exist)")
        return

    if not assume_yes:
        click.confirm(f"Remove '{name}' and everything under {target}?", abort=True)

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise click.ClickException(f"Could not remove '{name}' ({target}): {exc}") from exc
    click.echo(f"Removed '{name}' ({target})")
