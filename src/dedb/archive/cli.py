"""Click commands contributed by the archive app: `lsarchive` (list an
archive.org user's public favorites). archive.org games are named
`archive://<id>` and downloaded/run/converted by the generic commands
(see dedb.verbs, dedb.archive.backend). dedb.core.get_apps() reads
`commands`."""

import urllib.error

import click

from ..settings import SETTINGS_PATH, save_archive_favorites_user


def _resolve_user(user: str | None) -> str:
    """The archive.org screen name whose favorites to list: --user if
    given, else the configured [archive] favorites_user, else prompt for
    it and offer to save it."""
    if user:
        return user

    from ..core import get_settings

    configured = get_settings().archive.favorites_user
    if configured:
        return configured

    user = click.prompt("archive.org username whose favorites to list").strip()
    if not user:
        raise click.ClickException("No username given.")

    if click.confirm(f"Save this as favorites_user in {SETTINGS_PATH}?", default=True):
        try:
            save_archive_favorites_user(user)
        except OSError as exc:
            click.echo(f"Could not save to {SETTINGS_PATH}: {exc}", err=True)
        else:
            get_settings.cache_clear()
    return user


@click.command("lsarchive")
@click.option(
    "--favorites",
    "list_mode",
    flag_value="favorites",
    default=True,
    help="List the archive.org user's public favorites. (default)",
)
@click.option(
    "--user",
    "user",
    metavar="NAME",
    default=None,
    help="archive.org screen name to list, overriding the configured [archive] favorites_user.",
)
@click.option(
    "--dos/--all",
    "dos_only",
    default=True,
    help="--dos (default): only MS-DOS items. --all: every favorite.",
)
@click.option(
    "-1",
    "names_only",
    is_flag=True,
    default=False,
    help="Just `archive:<id>` per line - no title column.",
)
def lsarchive(list_mode: str, user: str | None, dos_only: bool, names_only: bool) -> None:
    """List an archive.org user's favorites as `archive:<id>` targets.

    The user is read from the [archive] favorites_user setting, or
    prompted for when unset. By default only MS-DOS items are shown;
    pass --all for every favorite.
    """
    from .client import favorite_items

    username = _resolve_user(user)

    try:
        items = favorite_items(username, dos_only=dos_only)
    except urllib.error.URLError as exc:
        raise click.ClickException(f"Could not reach archive.org: {exc}")
    except LookupError as exc:
        raise click.ClickException(str(exc))

    for item in items:
        if names_only:
            click.echo(f"archive:{item.identifier}")
        else:
            label = item.title or ""
            if item.year:
                label = f"{label} ({item.year})".strip()
            click.echo(f"{'archive:' + item.identifier:<50} {label}".rstrip())


commands = [lsarchive]
