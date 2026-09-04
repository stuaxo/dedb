"""Match game references against downloaded games with shell wildcards.

``dedb rm`` and ``dedb ls`` both accept game tokens that may be shell
wildcards - ``*``, ``?``, ``[...]`` - e.g. ``gog:tyrian*`` or ``doom?``.
:func:`match_downloads` turns one such token into the downloads it hits.

A token may carry a ``<scheme>:`` prefix (``gog:tyrian*``) to pin the
search to one backend; otherwise it is matched under every backend, or
under the one named by an explicit ``--backend``.
"""

import fnmatch
import re

from .registry import get_backends

_WILDCARD = re.compile(r"[*?\[]")


def has_wildcard(token: str) -> bool:
    """True if ``token`` contains a shell wildcard metacharacter."""
    return _WILDCARD.search(token) is not None


def match_downloads(pattern: str, *, backend: "str | None" = None, registry=None) -> list:
    """``(backend, identifier)`` pairs whose downloaded name matches the
    shell wildcard ``pattern``.

    Backends searched: just ``backend`` when given; the one named by a
    ``<scheme>:`` prefix on ``pattern``; otherwise all of them. A literal
    ``pattern`` (no metacharacters) simply matches that exact name.
    """
    registry = registry or get_backends()
    scheme, sep, bare = pattern.partition(":")
    if backend is not None:
        candidates = {backend: pattern}
    elif sep and scheme in registry:
        candidates = {scheme: bare.lstrip("/")}
    else:
        candidates = {name: pattern for name in registry}

    hits = []
    for name, pat in candidates.items():
        be = registry[name]
        hits += [(be, identifier) for identifier in fnmatch.filter(be.local_names(), pat)]
    return hits
