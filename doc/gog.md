# GOG

GOG (Good Old Games) have many games available that use DOSBOX, the gog
tools here extend the default DOSBOX tools and allow downloading, playing
and conversion of these games to DOSEMU2.

See `dosbox_to_dosemu.md` for general notes on mapping DOSBOX idioms to DOSEMU2


Each game lives at `<download_dir>/gog/<game_id>/`:

- `installer/` — deleted after conversion unless `--keep`
- `game/` — extracted install
- `metadata.json` — cached GOG metadata and launch profiles
- `dosemu/` — generated `dosemu.conf`/`userhook.bat`


## Configuration

`download_dir` is shared across every source dedb can pull games from (GOG, archive.org, ...)
- each gets its own namespaced subdirectory under it (`<download_dir>/gog/`, `<download_dir>/archive/`).
Set it by editing `~/.config/dedb/dedbconf.toml`:

```toml
download_dir = "/path/to/downloads"
```

`dedb run gog://<id> --dosbox` runs a game's own conf(s) unmodified through a real DOSBox. Which binary it uses is set under `[dosbox]`:

```toml
[dosbox]
dosbox = "default"
```

`"default"` picks the first installed of `dosbox_staging` or `dosbox`. Set it explicitly to pin a particular one - options are `dosbox`, `dosbox_staging`, `dosbox_x`, `dosbox_pure` (only `dosbox` and `dosbox_staging` have actually been tested so far).


## Commands

Most GOG work now goes through the generic, target-driven commands with a
`gog://<gamename>` target (see the main README):

```
$ dedb download gog://tyrian_2000
$ dedb run gog://tyrian_2000 --dosbox
$ dedb run 'gog://warcraft_orcs_and_humans?profile=server' --dosbox
$ dedb run tyrian_2000 -b gog --dosbox      # -b/--backend instead of the gog:// prefix
$ dedb import gog://tyrian_2000
$ dedb dosboxconf gog://tyrian_2000 --issues
$ dedb rm gog://tyrian_2000
```

Two GOG-specific commands remain (they have no generic-verb equivalent):

| Command       | Purpose                                                        |
|---------------|---------------------------------------------------------------- |
| `listgog`     | List the DOS games you own on GOG and how they're classified. |
| `downloadgog` | Bulk-download your whole DOS library; `--game <id>` for one.   |

`rungog`, `importgog`, `dosboxconfgog` and `rmgog` have been removed - use the
generic `dedb run|import|dosboxconf|rm gog://<id>` commands above.


### listgog

List owned GOG games.


### downloadgog

Download all owned GOG games:

```$ downloadgog```

Download a particular game:

1. List the owned games:

```$ listgog```

2. Download a single game (tyrian_2000):

```$ dedb download gog://tyrian_2000```

On initial download, a DOSEMU2 conf isn't created; `dedb import gog://<id>` can
do this, and `dedb run` also does it on demand.



# Run GOG game in DOSBOX

```$ dedb run gog://tyrian_2000 --dosbox```

This is a good baseline as this runs the unaltered game.


# Run GOG game in DOSEMU2

```$ dedb run gog://tyrian_2000 --dosemu```

Pick a launch profile with `gog://<id>?profile=<slug>` or `--profile <slug>` -
see profiles below.


## Profiles

GOG DOSBOX based games can multiple `dosbox*.conf` files, these are
alternate launch modes (e.g. to add netplay).

GOG games usually have metadataa in `goggame-*.info`, this list each mode as a `playTask`,
the default is marked with `isPrimary`.

If a game has no `goggame-*.info` file the default is that dosbox confs are merged.

We save dosemu conf files for each profile, though only the primary profile
is currently supported - others may have undefined behaviour.

For our purposes we are only interested in tasks that reference a `conf` file.

Ignored tasks reference tools like `GOGDOSConfig.exe` - a windows based tool
for configuring DOSBOX in GOG.


### Example Profile: warcraft_orcs_and_humans

| Conf | Role |
|---|---|
| `dosbox_warcraft.conf` | Base hardware settings |
| `dosbox_warcraft_single.conf` | Single player — the primary profile |
| `dosbox_warcraft_client.conf` | IPX client |
| `dosbox_warcraft_server.conf` | IPX server |
