# archive.org

archive.org's DOS software library (e.g.
https://archive.org/details/msdos_Electro_Man_1992) hosts thousands of
DOS games and utilities, each playable in-browser via DOSBox. Every
such item records, in its own metadata, which file to run - the tools
here download that file, extract it, and let it run through DOSBox or
DOSEMU2 the same way `gog`'s commands do for GOG games.

Unlike GOG, archive.org items aren't "owned" - there's no login and
nothing to list. Address one by `archive://<identifier>`, or paste its
full `https://archive.org/details/<identifier>` URL.

Each item lives at `<download_dir>/archive/<identifier>/`:

- `download/` — the fetched .zip, deleted after extraction unless `--keep`
- `game/` — extracted files
- `metadata.json` — cached archive.org item metadata
- `dosemu/` — generated `dosemu.conf`/`userhook.bat`


## How it works

An archive.org DOS item's metadata carries three fields:

- `emulator` — must be `dosbox`; other values (e.g. `scummvm`) aren't supported
- `emulator_ext` — the extension of the file to download (currently only `zip` is supported)
- `emulator_start` — the path, relative to that file's root, of the executable to run (e.g. `ElectroM/EM.EXE`)

That's the entire launch recipe: there's no `dosbox.conf` to parse. `dedb import`
takes DOSBox's own defaults (the same ones `importdosbox` falls back to for
settings a conf doesn't specify) and synthesizes a minimal autoexec from
`emulator_start` - mount the item's root as `C:`, `cd` into its directory, run it.
(`dedb dosboxconf archive://<id>` therefore has nothing to show and says so.)


## Configuration

`download_dir` is shared with `gog` (see `doc/gog.md`) - archive.org items live under
`<download_dir>/archive/`, GOG games under `<download_dir>/gog/`:

```toml
download_dir = "/path/to/downloads"
```

`dedb run archive://<id> --dosbox` uses the same `[dosbox]` binary selection as
GOG - see `doc/gog.md`.


## Commands

Name a game `archive://<identifier>` (a pasted `https://archive.org/details/<id>`
URL works too) and use the generic commands:

```
$ dedb download archive://msdos_Electro_Man_1992
$ dedb run archive://msdos_Electro_Man_1992 --dosbox
$ dedb run msdos_Electro_Man_1992 -b archive --dosbox   # -b/--backend form
$ dedb import archive://msdos_Electro_Man_1992
$ dedb rm archive://msdos_Electro_Man_1992
```


### Download

```$ dedb download archive://msdos_Electro_Man_1992```

or, with a full URL:

```$ dedb download https://archive.org/details/msdos_Electro_Man_1992```

On initial download, a DOSEMU2 conf isn't created - `dedb import archive://<id>`
does this, and `dedb run` also does it on demand.


### Run in DOSBox

```$ dedb run archive://msdos_Electro_Man_1992 --dosbox```

A good baseline, as this runs the item exactly as archive.org's own player would.


### Run in DOSEMU2

```$ dedb run archive://msdos_Electro_Man_1992 --dosemu```
