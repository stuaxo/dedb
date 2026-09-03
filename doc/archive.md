# archive.org

archive.org's DOS software library (e.g.
https://archive.org/details/msdos_Electro_Man_1992) hosts thousands of
in-browser DOSBox games. Each item's metadata names the file to run;
dedb downloads and extracts it and runs it under DOSBox or DOSEMU2, the
same as a GOG game.

archive.org items aren't "owned" - there's no login. Address one by
`archive://<identifier>` or its `https://archive.org/details/<identifier>`
URL. `dedb lsarchive` lists an archive.org user's public favorites as a
starting point.

Each item lives at `<download_dir>/archive/<identifier>/`:

- `download/` — the fetched .zip, deleted after extraction unless `--keep`
- `game/` — extracted files
- `metadata.json` — the shared metadata envelope (`dedb.core.metadata_file`); the raw
  archive.org item metadata is under `source`
- `dosemu/` — generated `dosemu.conf`/`userhook.bat`


## How it works

An archive.org DOS item's metadata carries three fields:

- `emulator` — must be `dosbox`; other values (e.g. `scummvm`) aren't supported
- `emulator_ext` — the extension of the file to download (currently only `zip` is supported)
- `emulator_start` — the path, relative to that file's root, of the executable to run (e.g. `ElectroM/EM.EXE`)

There's no `dosbox.conf`. emularity launches an item by synthesising a `dosbox`
command line from `emulator_start`: mount the item root as `C:`, `cd` to the
game's directory, run the file. dedb rebuilds that command line and runs it
through the same models a GOG game's `dosbox.conf` goes through
(`dedb.dosbox.cmdline`), so `dedb import` produces `dosemu.conf` (DOSBox
defaults) plus `userhook.bat`, and `dedb dosboxconf archive://<id>` shows the
autoexec, the settings and any conversion issues - the item must be downloaded
first.


## Configuration

`download_dir` is shared with `gog` (see `doc/gog.md`) - archive.org items live under
`<download_dir>/archive/`, GOG games under `<download_dir>/gog/`:

```toml
download_dir = "/path/to/downloads"
```

`dedb run archive://<id> --dosbox` uses the same `[dosbox]` binary selection as
GOG - see `doc/gog.md`.

`[archive]` holds one archive-specific setting, `archive_user` - the
archive.org screen name `dedb lsarchive` lists favorites for:

```toml
[archive]
archive_user = "your-archive-org-username"
```

When it's unset, `lsarchive` prompts for the name and offers to save it here.


## Commands

Name a game `archive://<identifier>`, or paste its
`https://archive.org/details/<id>` URL, then:

```
$ dedb download archive://msdos_Electro_Man_1992
$ dedb run archive://msdos_Electro_Man_1992 --dosbox
$ dedb run msdos_Electro_Man_1992 -b archive --dosbox   # -b instead of the prefix
$ dedb import archive://msdos_Electro_Man_1992
$ dedb rm archive://msdos_Electro_Man_1992
```

`dedb run` downloads the game and, for `--dosemu`, converts it, if that hasn't
happened yet.


### List a user's favorites

```
$ dedb lsarchive                       # the configured archive_user, MS-DOS items only
$ dedb lsarchive --user someone        # a different archive.org user
$ dedb lsarchive --all                 # include non-DOS favorites
$ dedb lsarchive -1                    # bare `archive:<id>` lines
```

archive.org files every account's favorites under a `fav-<username>`
collection; `lsarchive` queries it through the public advancedsearch
API (no login) and, by default, intersects it with archive.org's
`softwarelibrary_msdos` / `softwarelibrary_msdos_games` collections so
only DOS items show. Feed the output straight into `dedb download` or
`dedb run`.


### Run in DOSBox

```$ dedb run archive://msdos_Electro_Man_1992 --dosbox```

Runs the game as archive.org's own player would.


### Run in DOSEMU2

```$ dedb run archive://msdos_Electro_Man_1992 --dosemu```
