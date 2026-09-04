"""CLI-argument helpers shared across the command modules.

Handling for a ``SOURCES`` argument that is *either* one or more
dosbox.conf paths *or* a single downloaded game reference
(``gog:<id>`` / ``archive:<id>``, a GOG or archive.org page URL, or a
bare id with ``-b``), used by ``dedb dosboxconf``, ``dedb dosemuconf`` and ``dedb
import``; plus ``cli_command``, which turns the domain layer's
user-facing exceptions into a one-line click error.
"""

import functools
from pathlib import Path
from urllib.parse import urlparse

import click
from click.shell_completion import CompletionItem

from .backends import GameRefError, complete_target
from .downloader import DownloadError
from .layout import UnsafePathError
from .registry import get_backends
from .settings import ConfigError

# Failures that are part of normal use: a game reference that doesn't
# resolve, a game that isn't downloaded, an unsupported archive.org item,
# a launch profile that doesn't exist, a pre-existing output directory, a
# download that fell over, missing configuration. `cli_command` renders
# these as `Error: <message>`; anything outside this set keeps its
# traceback, because at that point dedb really is broken.
#
# GameRefError, UnsafePathError and DownloadError sit on stdlib bases too
# broad to catch here (ValueError / RuntimeError), so they're named.
# FileNotFoundError / FileExistsError are precise enough to catch as-is
# (they cover NotDownloadedError and the missing-conf / output-exists
# cases). LookupError is the one broad base kept on purpose: it covers
# gog.ProfileError and archive.NotDosItemError without this core module
# importing those app packages.
USER_FACING_ERRORS = (
    GameRefError,
    UnsafePathError,
    DownloadError,
    ConfigError,
    FileNotFoundError,
    FileExistsError,
    LookupError,
)


def cli_command(func):
    """Decorator for a click command body: convert a `USER_FACING_ERRORS`
    into a `click.ClickException` (a one-line ``Error:`` message, exit 1).
    Apply it directly above the function, below the click decorators."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except click.ClickException:
            raise
        except USER_FACING_ERRORS as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper


def is_game_ref(source: str) -> bool:
    """True if ``source`` is a ``<scheme>:<id>`` (any number of slashes) or
    an http(s) game URL (a GOG or archive.org page) - something
    ``resolve_game`` handles, not a file path."""
    scheme = urlparse(source).scheme  # "" for a bare path, "gog" for gog:x or gog://x
    return scheme in get_backends() or scheme in ("http", "https")


def existing_conf(source: str) -> Path:
    """``source`` as a Path, or a ``BadParameter`` pointing at the game-ref
    form if it is not an existing file."""
    path = Path(source)
    if not path.is_file():
        raise click.BadParameter(
            f"{source!r} is not an existing dosbox.conf. For a downloaded game, pass "
            f"'gog:<id>' / 'archive:<id>' (or a bare id with --backend)."
        )
    return path


def complete_source(ctx, param, incomplete):
    """Shell completion for such a SOURCES argument: ``<scheme>:<id>``
    targets (honouring ``-b``), and - unless a scheme is already typed -
    file paths as well."""
    targets = complete_target(incomplete, backend=ctx.params.get("backend"))
    if is_game_ref(incomplete) or ctx.params.get("backend"):
        return targets
    return [*targets, CompletionItem(incomplete, type="file")]
