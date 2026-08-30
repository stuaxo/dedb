# dedb

DOSEMU2-DOSBOX importer and run games packaged for DOSBOX in DOSEMU2.


## Core commands

List the subcommands:
`$ dedb`

List downloaded games:
`$ dedb ls`

`dedb ls` prints one game per line. A name gets a `<scheme>:` prefix when it
exists under more than one backend. `-1` prints bare names. `-l` prints every
game as a `<scheme>:<id>` URL, for piping into `dedb run` or `dedb rm`.

Filter by backend (repeatable, or comma-separated):
`$ dedb ls --type=gog`
`$ dedb ls --type=gog,archive`


### Naming a game

`dedb run`, `download`, `import` and `rm` take one GAME argument:

| GAME                              | Is                                             |
|-----------------------------------|------------------------------------------------|
| `gog:<gamename>`                  | a GOG game (the lgogdownloader gamename slug)   |
| `gog:<gamename>?profile=<slug>`   | a GOG launch profile                            |
| `archive:<identifier>`            | an archive.org item                             |
| `https://archive.org/details/<id>`| an archive.org item, by URL                     |
| `<name>`                          | a downloaded game, by name                      |

```
$ dedb run gog://tyrian_2000 --dosbox
$ dedb run archive://msdos_Electro_Man_1992 --dosemu
$ dedb run 'gog://warcraft_orcs_and_humans?profile=server' --dosbox -- -fullscreen
$ dedb download gog://tyrian_2000
$ dedb rm gog://tyrian_2000
```

Slashes after the colon are optional: `gog:x`, `gog://x` and `gog:///x` are the
same.

A bare name works only when the game is downloaded under one backend. Otherwise
add the scheme, as a prefix or with `-b`:

```
$ dedb run tyrian_2000 -b gog --profile server --dosbox
```

`-b <scheme>` with a bare id is `<scheme>://<id>`. `--profile` is `?profile=`.

To add a backend, see [doc/backends.md](doc/backends.md).


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

Name a game `gog://<gamename>`, then use `dedb download`, `run`, `import`, `rm`
or `dosboxconf` (see Naming a game above and `doc/gog.md`). `listgog` lists your
DOS games on GOG; `downloadgog` downloads all of them.

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

Run DOS games from archive.org's software library
(e.g. https://archive.org/details/msdos_Electro_Man_1992). There is no login.

Games live under `<download_dir>/archive/` - see Configuration above.

Name a game `archive://<identifier>`, or paste its
`https://archive.org/details/<id>` URL, then use `dedb download`, `run`,
`import` or `rm` (see Naming a game above and `doc/archive.md`).