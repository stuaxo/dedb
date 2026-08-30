# Backends

A **backend** is a source of DOSBox games. A game is named by a URL scheme:
`gog://<gamename>`, `archive://<identifier>`. The generic commands
(`dedb run|download|import|rm GAME`, and `dedb dosboxconf`) resolve GAME to a
backend and dispatch to it.

Every generic command also accepts the URL's parts as options instead of a
prefix (the way `psql` takes a URI *or* `-h/-U/-d`): `-b/--backend <scheme>`
plus a bare id is exactly `<scheme>://<id>`, and `--profile <slug>` is
`?profile=<slug>`. Passing both a `scheme://` URL and `-b` is an error.

## How resolution works

`dedb.backends.resolve(value)` turns whatever the user typed into a `Target`
(backend + game id + profile):

1. `<scheme>:<id>` (optionally `?profile=<slug>`) - looked up directly in the
   registry. The id is not a host, so the slashes after the colon are optional
   and cosmetic: `gog:tyrian_2000`, `gog://tyrian_2000` and `gog:///tyrian_2000`
   are the same game.
2. `http(s)://...` - each backend is asked `identifier_from_url(url)`; the first
   to recognise it wins (archive.org item pages, say).
3. a bare name - matched against every backend's local downloads
   (`<download_dir>/<scheme>/<name>`). Exactly one hit resolves; several is an
   error asking for a scheme; zero produces a `Did you mean: dedb run <name>`
   suggestion when a local name is a unique prefix/substring of what was typed,
   or a close `difflib` near-miss. Stdlib only - no fuzzy-match dependency.

`resolve()` never hits the network.

## Adding a backend

1. Create `src/dedb/<app>/backend.py`:

   ```python
   from dataclasses import dataclass
   from ..backends import BackendBase, Target, register_backend

   @register_backend("myscheme")
   @dataclass(frozen=True)
   class MyBackend(BackendBase):
       scheme: str = "myscheme"
       supports_profile: bool = False

       def layout(self, identifier): ...
       def ensure_downloaded(self, identifier, *, keep, refresh_metadata, redownload): ...
       def run(self, target: Target, layout, *, emulator, extra_args, verbose) -> int: ...
       def convert(self, target: Target, *, output_dir=None, force=False): ...
       def build(self, target: Target): ...   # [(label, dosemu_conf_text, userhook_lines)]
   ```

   `BackendBase` already provides `is_downloaded`, `local_names`, `remove`, a
   no-op `identifier_from_url` (override only if your backend owns an http(s) URL
   shape), and a `dosbox_sources` that raises "no dosbox.conf" (override if your
   items ship one, for `dedb dosboxconf`).

2. List `"dedb.<app>"` in `Settings.apps`. `dedb.core.get_backends()` auto-imports
   `dedb.<app>.backend`; `DOWNLOAD_BACKENDS` and `dedb ls` pick it up from the
   registry. (`get_apps()` also imports `dedb.<app>.cli` for its `commands` list;
   that list may be empty.)

3. Keep `backend.py` import-light - do runner/importer imports inside the
   method bodies. It is imported when the CLI starts.

## Command behaviour

`dedb download <scheme>://<id>` is a no-op when the game is already present,
unless `--redownload` or `--refreshmetadata` is given.

A backend may also contribute account-level commands through its `cli.py`
(e.g. GOG's `listgog` and `downloadgog`, which act on your library rather than
one game).
