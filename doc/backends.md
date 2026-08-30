# Backends

A backend is a source of DOS games. Each game has a URL: `gog://<gamename>` or
`archive://<identifier>`.

`dedb run`, `download`, `import`, `rm` and `dosboxconf` take a game URL and
dispatch to its backend. You can give the parts separately instead: `-b <scheme>`
with a bare id, and `--profile <slug>` for `?profile=`. Giving both a `scheme://`
URL and `-b` is an error.

## Resolving a game

`dedb.backends.resolve()` turns the argument into a `Target` (backend, id,
profile).

- `<scheme>:<id>` (optionally `?profile=<slug>`) - read from the registry.
  Slashes after the colon don't matter: `gog:x`, `gog://x` and `gog:///x` are
  the same game.
- `http(s)://...` - offered to each backend's `identifier_from_url()`. The
  archive backend recognises `archive.org` item URLs.
- A bare name - matched against downloaded games in `<download_dir>/<scheme>/`.
  One match resolves. Several is an error. None gives a "did you mean" if a name
  is close (unique prefix, unique substring, or `difflib` near-miss).

`resolve()` does not use the network.

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

   `BackendBase` provides `is_downloaded`, `local_names` and `remove`. Override
   `identifier_from_url` if the backend has its own URL form, and `dosbox_sources`
   if its games ship a `dosbox.conf`.

2. Add `"dedb.<app>"` to `Settings.apps`. `get_backends()` imports
   `dedb.<app>.backend`; `dedb ls` and `DOWNLOAD_BACKENDS` pick it up.

3. Keep `backend.py` cheap to import - put `runner` / `importer` imports inside
   the methods.

## Downloading

`dedb download <url>` does nothing if the game is already downloaded. Pass
`--redownload` or `--refreshmetadata` to force it.

A backend can add library-level commands in its `cli.py`, like GOG's `lsgog`
and `downloadgog`.
