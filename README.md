# dedb

DOSEMU2-DOSBOX importer and run games packaged for DOSBOX in DOSEMU2.


## Core commands

List all the available subcommands.
`$ dedb`

List locally-downloaded games/items, by name, across download backends.
`$ dedb list`

Filter to specific backends - repeatable and/or comma-separated:
`$ dedb list --type=gog --type=archive`
`$ dedb list --type=archive,gog`

Add `-1` for one bare name per line (no per-backend headings).


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

Commands: `downloadgog`, `listgog`, `importgog`, `rungog`. See `dedb <command> --help`.

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


`importgog`/`rungog` take `--profile <name-or-slug>` to pick a non-default
one; `importgog` with no `--profile` converts every valid profile, writing
the default as `dosemu.conf`/`userhook.bat` and others as
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

Commands: `downloadarchive`, `importarchive`, `runarchive`. See `dedb <command> --help` and `doc/archive.md`.