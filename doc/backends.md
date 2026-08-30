# Backends

A **backend** is a source of DOSBox games addressed by a URL scheme:
`gog://<gamename>`, `archive://<identifier>`. The generic commands
(`dedb run|download|import|rm <target>`, and `dedb dosboxconf`) resolve a target
to a backend and dispatch to it.

Every generic command also accepts the URL's parts as options instead of a
prefix (the way `psql` takes a URI *or* `-h/-U/-d`): `-b/--backend <scheme>`
plus a bare id is exactly `<scheme>://<id>`, and `--profile <slug>` is
`?profile=<slug>`. Passing both a `scheme://` target and `-b` is an error.

## How resolution works

`dedb.backends.resolve(value)` turns whatever the user typed into a `Target`:

1. `<scheme>://<id>` (optionally `?profile=<slug>`) - looked up directly in the
   registry.
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

2. Add `"dedb.<app>"` to `Settings.apps` (it already needs to be there to
   contribute CLI commands). `dedb.core.get_backends()` auto-imports
   `dedb.<app>.backend`; `DOWNLOAD_BACKENDS` and `dedb list` pick it up from the
   registry.

3. Keep `backend.py` import-light - do runner/importer imports inside the
   method bodies. It is imported when the CLI starts.

## Deprecated per-backend commands

The old per-backend verbs are deprecated aliases of the generic commands - they
still work, warn on stderr, and will be removed later:

| Old                                              | New                          |
|--------------------------------------------------|------------------------------|
| `rungog`, `runarchive`                           | `dedb run <scheme>://<id>`   |
| `importgog`, `importarchive`                     | `dedb import <scheme>://<id>`|
| `dosboxconfgog`                                  | `dedb dosboxconf gog://<id>` |
| `rmgog`, `rmarchive`, `downloadarchive`          | `dedb rm` / `dedb download`  |

Kept: `listgog` (lists owned GOG games - no target), `downloadgog` (bulk library
download), `importdosbox` / `dedb dosboxconf <file>` (operate on raw `.conf`
paths).

Note: `dedb download <scheme>://<id>` is a no-op when the game is already present
(unless `--redownload` / `--refreshmetadata`), whereas the old `downloadarchive`
always re-ran extraction.
