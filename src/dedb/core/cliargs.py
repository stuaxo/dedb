"""Shared handling for a ``SOURCES`` argument that is *either* one or more
dosbox.conf paths *or* a single downloaded game reference
(``gog:<id>`` / ``archive:<id>``, an archive.org URL, or a bare id with
``-b``). Used by ``dedb dosboxconf``, ``dedb dosemuconf`` and ``dedb
import``.
"""

from pathlib import Path
from urllib.parse import urlparse

import click
from click.shell_completion import CompletionItem

from .backends import complete_target
from .registry import get_backends


def is_game_ref(source: str) -> bool:
    """True if ``source`` is a ``<scheme>:<id>`` (any number of slashes) or
    an archive.org item URL - something ``resolve_game`` handles, not a
    file path."""
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
