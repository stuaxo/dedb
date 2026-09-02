"""Operations on the downloads tree: resolving an app's namespaced
subdir under ``[download_dir]`` (with the policy about when to create it),
and the shared ``dedb rm`` implementation.

The pure "where is it" part is ``Settings.download_dir_for``; this module
is the part that also touches the filesystem and reports errors.
"""

import tempfile
from pathlib import Path

import click

from . import settings
from .layout import LayoutPaths


def require_download_dir(app_name: str) -> Path:
    """The app's ``<download_dir>/<scheme>`` subdir (see
    ``Settings.download_dir_for``), raising a ClickException when
    [download_dir] isn't configured - for commands that can't do anything
    without it. Doesn't check the directory exists; the download path uses
    ensure_download_dir for that."""
    app_dir = settings.get_settings().download_dir_for(app_name)
    if app_dir is None:
        raise click.ClickException(
            f"download_dir is not set. Add it to {settings.SETTINGS_PATH}, e.g.:\n"
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


def remove_download(layout: LayoutPaths, *, assume_yes: bool) -> None:
    """Shared implementation of `dedb rm`: delete a downloaded game/item's
    whole directory tree, after confirming. The safety checks live in
    `LayoutPaths._safe_rmtree`."""
    if not layout.dir.exists():
        click.echo(f"Nothing to remove for '{layout.dir.name}' ({layout.dir} doesn't exist)")
        return
    if not assume_yes:
        click.confirm(f"Remove '{layout.dir.name}' and everything under {layout.dir}?", abort=True)
    try:
        layout.rm()
    except OSError as exc:
        raise click.ClickException(
            f"Could not remove '{layout.dir.name}' ({layout.dir}): {exc}"
        ) from exc
    click.echo(f"Removed '{layout.dir.name}' ({layout.dir})")
