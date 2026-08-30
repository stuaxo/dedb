# dedb

DOSEMU2-DOSBOX importer and run games packaged for DOSBOX in DOSEMU2.


## Core commands

List all the available subcommands.
`$ dedb`

List locally-downloaded games/items, across download backends.
`$ dedb ls`

By default each game is a bare name, one per line; a name gets a `<scheme>:`
prefix only when the *same* name exists under more than one backend. `-1` prints
bare names only; `-l` prints every entry as a full `<scheme>:<id>` URL
(pasteable into `dedb run`, `dedb rm`, ...).

Filter to specific backends - repeatable and/or comma-separated:
`$ dedb ls --type=gog --type=archive`
`$ dedb ls --type=archive,gog`


### Naming a game

`dedb run`, `download`, `import` and `rm` all take one GAME argument. It can be:

| GAME                              | Means                                          |
|-----------------------------------|------------------------------------------------|
| `gog:<gamename>`                  | a GOG game (the lgogdownloader gamename slug)   |
| `gog:<gamename>?profile=<slug>`   | a specific GOG launch profile                   |
| `archive:<identifier>`            | an archive.org item                             |
| `https://archive.org/details/<id>`| same, as a pasted item URL                      |
| `<name>`                          | a bare name - resolved against local downloads  |

The slashes after the colon are optional - `gog:x`, `gog://x` and `gog:///x` are
the same (the id isn't a host). `gog://` reads most naturally in a shell.

```
$ dedb run gog://tyrian_2000 --dosbox
$ dedb run archive://msdos_Electro_Man_1992 --dosemu
$ dedb run 'gog://warcraft_orcs_and_humans?profile=server' --dosbox -- -fullscreen
$ dedb download gog://tyrian_2000
$ dedb import archive://msdos_Electro_Man_1992
$ dedb rm gog://tyrian_2000
```

A bare name (no scheme) only resolves once the game is downloaded and lives
under exactly one backend; otherwise prefix it with `gog://` / `archive://`, or
pass the scheme as an option instead of a prefix (like `psql` taking either a
URI or separate `-h/-U/-d`):

```
$ dedb run tyrian_2000 -b gog --profile server --dosbox
```

`-b/--backend <scheme>` + a bare id is exactly `<scheme>://<id>`; `--profile`
is the same as `?profile=<slug>`.

To add a backend of your own, see [doc/backends.md](doc/backends.md).


## Configuration

Downloaded games/items live under one shared `download_dir`, namespaced per source
(`<download_dir>/gog/`, `<download_dir>/archive/`, ...). Set it by editing
`~/.config/dedb/dedbconf.toml`:

```toml
download_dir = "/path/to/downloads"
```


## Good Old Games (GOG)

Import and run directly from GoG (Good Old Games).

GOG marks DOS games as "Windows" with a dependency on DOSBOX, `dedb` uses `lgogdownloader` to search for Windows games 
and then does a metadata query to find the DOSBOX dependency.

Data is cached locally to avoid hitting GOG more than is nessacary.



Dependencies:

# On Debian / Ubuntu run:

`sudo apt install lgogdownloader innoextract`


Games live under `<download_dir>/gog/` - see Configuration above.

Name a game `gog://<gamename>` and use the generic commands: `dedb download`,
`dedb import`, `dedb run`, `dedb rm`, `dedb dosboxconf` (see Naming a game above
and `doc/gog.md`). The only GOG-specific commands are `listgog` (lists your owned
DOS games) and `downloadgog` (bulk-downloads your whole library).

### Launch profiles

Games from GOG can ship multiple `dosbox*.conf` files, each one is a profile,
e.g. to change the hardware profile or add multiplayer networking.

The primary conf is exported to `dosemu.conf` others are named per profile,
e.g. `dosemu_<profile>.conf`.


### Non-Primary Profiles:

[Partially supported]

These are not fully supported:

Profiles can provide their own [autoexec], but only the primary autoexec is currently used for now,
expect undefined behaviour using them.


`dedb run`/`dedb import` take `--profile <name-or-slug>` (or
`gog://<id>?profile=<slug>`) to pick a non-default one; `dedb import` with no
`--profile` converts every valid profile, writing the default as
`dosemu.conf`/`userhook.bat` and others as
`dosemu_<profile>.conf`/`userhook_<profile>.bat`.

For example, `warcraft_orcs_and_humans` has:

| Conf                        | Purpose                |
|-----------------------------|------------------------|
| dosbox_warcraft.conf        | Base hardware settings |
| dosbox_warcraft_single.conf | Single player          |
| dosbox_warcraft_client.conf | IPX client             |
| dosbox_warcraft_server.conf | IPX server             |


### GOGDOSConfig configured games:

Game profiles configured by GOGDOSConfig, these games are shipped without a `playTask` entry, these are currently
ignored.


## archive.org

Download, import and run DOS games/software hosted on archive.org's software library
(e.g. https://archive.org/details/msdos_Electro_Man_1992), identified either by their
archive.org identifier or their full item URL.

Unlike GOG, archive.org items aren't owned - each command just takes an item directly,
no login required.

Items live under `<download_dir>/archive/` - see Configuration above.

archive.org has no commands of its own - name a game `archive://<identifier>` (or
paste its `https://archive.org/details/<id>` URL) and use the generic commands:
`dedb download`, `dedb import`, `dedb run`, `dedb rm` (see Naming a game above
and `doc/archive.md`).