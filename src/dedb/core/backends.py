"""Backend registry and game-reference resolution.

A "backend" is a source of DOSBox games - GOG, archive.org, ... - and a
game is named by a URL: ``gog://<gamename>``, ``archive://<identifier>``,
optionally ``gog://<id>?profile=<slug>``. An ``https://archive.org/details/...``
URL, or a bare name that matches a local download, resolves too.

Each backend is a small frozen-dataclass class registered with
``@register_backend("<scheme>")`` (see dedb.gog.backend / dedb.archive.backend).
``dedb.core.get_backends()`` imports those modules and returns the registry.

This module deliberately imports nothing from ``dedb`` at module level - the
backend classes and ``resolve()`` reach into ``dedb.core`` (and each backend's
own runner/importer) with function-local imports, so importing ``dedb.core.backends``
stays cycle-free and cheap.
"""

import difflib
from dataclasses import dataclass
from importlib import import_module
from urllib.parse import parse_qs, urlparse

import click


def short_target(scheme: str, identifier: str) -> str:
    """``<scheme>:<identifier>`` - the compact game reference."""
    return f"{scheme}:{identifier}"


def long_target(scheme: str, identifier: str) -> str:
    """``<scheme>://<identifier>`` - the URL-style game reference."""
    return f"{scheme}://{identifier}"


# scheme -> backend instance. Populated by register_backend, which each
# dedb.<app>.backend module calls at import time.
_REGISTRY: "dict[str, BackendBase]" = {}


def register_backend(scheme: str):
    """Class decorator: instantiate the (zero-required-arg) backend class
    and store it under ``scheme``. Returns the class unchanged."""

    def decorator(cls: "type[BackendBase]") -> "type[BackendBase]":
        _REGISTRY[scheme] = cls()
        return cls

    return decorator


class BackendBase:
    """Behaviour shared by every backend. Subclasses are frozen dataclasses
    that set the ``scheme`` / ``supports_profile`` fields, point ``layout_cls``
    / ``runner_module`` / ``_downloader()`` at their own code, and fill the
    ``_import`` / ``build`` hooks. The rest have working defaults."""

    scheme: str
    supports_profile: bool = False
    layout_cls: type  # the backend's LayoutPaths subclass
    runner_module: str  # dotted path to the backend's runner (run_dosbox/run_dosemu)

    # --- URL recognition -------------------------------------------------

    def identifier_from_url(self, url: str) -> "str | None":
        """If ``url`` is an external http(s) URL this backend owns (e.g.
        an archive.org item page), return the bare identifier, else None."""
        return None

    # --- filesystem state ----------------------------------------------

    def layout(self, identifier: str):
        """The backend's layout for ``identifier`` (download_dir must be set)."""
        from . import require_download_dir

        return self.layout_cls(require_download_dir(self.scheme), identifier)

    def is_downloaded(self, identifier: str) -> bool:
        return self.layout(identifier).is_downloaded()

    def local_names(self) -> "list[str]":
        """Names of everything downloaded under this backend, for bare-name
        target resolution."""
        from . import get_download_dir

        root = get_download_dir(self.scheme)
        if root is None or not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    def remove(self, identifier: str, *, assume_yes: bool) -> None:
        from . import remove_download

        remove_download(self.layout(identifier), assume_yes=assume_yes)

    # --- actions -------------------------------------------------------

    def _downloader(self):
        """The backend's `dedb.core.downloader.Downloader` subclass, ready to use."""
        raise NotImplementedError

    def ensure_downloaded(
        self, identifier: str, *, keep: bool, refresh_metadata: bool, redownload: bool
    ):
        """Download + extract ``identifier`` if needed; return its layout."""
        from . import ensure_download_dir

        layout = self.layout_cls(ensure_download_dir(self.scheme), identifier)
        self._downloader().ensure(
            layout, keep=keep, refresh_metadata=refresh_metadata, redownload=redownload
        )
        return layout

    def run(self, target: "Target", layout, *, emulator: str, extra_args, verbose: bool) -> int:
        """Launch ``target`` in ``emulator`` ("dosbox" or "dosemu") via the
        backend's ``runner_module``; return the exit code."""
        runner = import_module(self.runner_module)
        launch = runner.run_dosbox if emulator == "dosbox" else runner.run_dosemu
        return launch(layout, target, extra_args, verbose)

    def convert(self, target: "Target", *, output_dir=None, force: bool = False):
        """Convert an already-downloaded ``target`` to DOSEMU2 config(s);
        return the directory they were written to."""
        layout = self.layout(target.identifier)
        self._import(layout, target, output_dir, force=force)
        return output_dir or layout.dosemu

    def _import(self, layout, target: "Target", output_dir, *, force: bool) -> None:
        """Write ``layout``'s DOSEMU2 config(s) into ``output_dir`` (or, when
        None, the layout's own ``dosemu/`` dir). Backend-specific."""
        raise NotImplementedError

    def build(self, target: "Target") -> "list[tuple[str, str, list[str]]]":
        """Like convert(), but return the content instead of writing it:
        ``[(label, dosemu_conf_text, userhook_lines), ...]`` - one entry
        per launch profile (GOG), or a single ("default", ...) entry."""
        raise NotImplementedError

    def dosbox_sources(self, target: "Target") -> "tuple[list, object]":
        """The dosbox.conf file(s) for ``target`` and the working directory
        their relative MOUNTs resolve against, for `dedb dosboxconf`.
        Backends whose games have no dosbox.conf (archive.org) raise."""
        raise click.ClickException(f"{self.scheme}:// games have no dosbox.conf to inspect.")


@dataclass(frozen=True)
class Target:
    """A resolved game reference: which backend, which game, and (GOG
    only) which launch profile. ``raw`` is the string the user typed."""

    scheme: str
    identifier: str
    profile: "str | None"
    raw: str

    @property
    def url(self) -> str:
        base = long_target(self.scheme, self.identifier)
        return f"{base}?profile={self.profile}" if self.profile else base


def _closest_name(value: str, names: "list[str]") -> "str | None":
    """Best "did you mean" for a bare name that matched nothing. A unique
    case-insensitive prefix or substring wins (catches abbreviations like
    "jazz" -> "jazz_jackrabbit_collection"); otherwise fall back to
    difflib's near-miss ratio (catches typos like "tyrian_200"). Uses only
    the stdlib - no fuzzy-match dependency."""
    lowered = value.lower()
    for candidates in (
        [n for n in names if n.lower().startswith(lowered)],
        [n for n in names if lowered in n.lower()],
    ):
        if len(candidates) == 1:
            return candidates[0]

    close = difflib.get_close_matches(value, names, n=1, cutoff=0.6)
    return close[0] if close else None


def _finish(backend: BackendBase, identifier: str, profile: "str | None", raw: str) -> Target:
    if profile is not None and not backend.supports_profile:
        raise click.ClickException(
            f"{backend.scheme}:// games have no launch profiles (drop --profile)."
        )
    return Target(backend.scheme, identifier, profile, raw)


def resolve(value: str, *, profile: "str | None" = None) -> Target:
    """Turn a user-supplied game reference into a :class:`Target`.

    Accepts ``<scheme>:<id>`` with any number of slashes after the colon
    (``gog:x``, ``gog://x``, ``gog:///x`` are equivalent - the id isn't a
    host), optionally ``?profile=<slug>``; an ``https://archive.org/...``
    item URL; or a bare name that matches a local download under exactly
    one backend. ``profile`` (the --profile flag) overrides any
    ``?profile=`` in the URL. Raises ``click.ClickException`` if nothing
    resolves.
    """
    from . import get_backends

    registry = get_backends()
    parsed = urlparse(value)
    scheme = parsed.scheme  # urlparse lowercases the scheme; netloc/path keep case

    if scheme in ("http", "https"):
        for backend in registry.values():
            identifier = backend.identifier_from_url(value)
            if identifier is not None:
                return _finish(backend, identifier, profile, value)
        raise click.ClickException(
            f"Don't know how to handle URL: {value}\nUse a scheme instead, e.g. archive://<id>."
        )

    if scheme in registry:
        backend = registry[scheme]
        # gog:x -> path, gog://x -> netloc, gog:///x -> path; all mean the same.
        identifier = (parsed.netloc or parsed.path.lstrip("/")).rstrip("/")
        if not identifier:
            raise click.ClickException(f"No game id in '{value}'")
        url_profile = parse_qs(parsed.query).get("profile", [None])[0]
        return _finish(backend, identifier, profile if profile is not None else url_profile, value)

    if scheme:
        known = ", ".join(f"{s}://" for s in sorted(registry))
        raise click.ClickException(f"Unknown scheme '{scheme}://'. Known schemes: {known}")

    # Bare name -> match against local downloads.
    local = {backend: backend.local_names() for backend in registry.values()}
    hits = [backend for backend, names in local.items() if value in names]
    if len(hits) == 1:
        return _finish(hits[0], value, profile, value)

    schemes = sorted(registry)
    if not hits:
        lines = [f"'{value}' isn't a URL and isn't downloaded under any backend."]
        all_names = sorted({name for names in local.values() for name in names})
        suggestion = _closest_name(value, all_names)
        if suggestion is not None:
            lines.append(f"Did you mean:  dedb run {suggestion}")
        lines.append(
            "Otherwise prefix it with a scheme, e.g. "
            + " or ".join(long_target(s, value) for s in schemes)
        )
        raise click.ClickException("\n".join(lines))
    found = sorted(backend.scheme for backend in hits)
    raise click.ClickException(
        f"'{value}' is downloaded under multiple backends ({', '.join(found)}).\n"
        f"Disambiguate with a scheme, e.g. {long_target(found[0], value)}"
    )


def resolve_game(
    value: str, backend: "str | None" = None, *, profile: "str | None" = None
) -> Target:
    """:func:`resolve`, plus the ``-b/--backend`` shorthand used by the CLI
    verbs: ``resolve_game("x", "gog")`` means ``resolve("gog://x")``. A
    ``backend`` and a ``<scheme>://`` URL in ``value`` are mutually
    exclusive. Raises ``click.UsageError`` for a bad ``--backend``."""
    from . import get_backends

    if backend is not None:
        registry = get_backends()
        if backend not in registry:
            raise click.UsageError(f"Unknown backend '{backend}'. Known: {', '.join(registry)}.")
        if "://" in value:
            raise click.UsageError("Give a <scheme>://<id> URL or --backend, not both.")
        value = long_target(backend, value)
    return resolve(value, profile=profile)
