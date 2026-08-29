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

`rungog --dosbox` runs games' own conf(s) unmodified through a real DOSBox. Which binary it uses is set under `[dosbox]`:

```toml
[dosbox]
dosbox = "default"
```

`"default"` picks the first installed of `dosbox_staging` or `dosbox`. Set it explicitly to pin a particular one - options are `dosbox`, `dosbox_staging`, `dosbox_x`, `dosbox_pure` (only `dosbox` and `dosbox_staging` have actually been tested so far).


## Commands

GOG Commands, these all operate on games you own on GOG.

| Command        | Description                                                   |
|----------------|---------------------------------------------------------------|
| `downloadgog`  | Download and extract DOSBOX games from GOG.                   |
| `listgog`      | List DOSBOX games on GOG                                      |
| `importgog`    | Create a DOSEMU2 conf and userhook from a downloaded GOG Game |
| `rungog`       | Run a GOG game in DOSBox or DOSEMU2.                          |
| `dosboxconfgog`| View config, autoexec and sound settings.                     |
| `rmgog`        | Delete a downloaded game's directory.                        |


### listgog

List owned GOG games.


### downloadgog

Download all owned GOG games:

```$ downloadgog```

Download a particular game:

1. List the owned games:

```$ listgog```

2. Download a single game (tyrian_2000):

```$ downloadgog tyrian_2000```

On initial download, a DOSEMU2 conf isn't created, `importgog` can do this for every game.
`rungog` also does this on demand.



# Run GOG game in DOSBOX

```$ rungog tyrian_2000 --dosbox```

This is a good baseline as this runs the unaltered game.


# Run GOG game in DOSEMU2

```$ rungog tyrian_2000 --dosemu```

rungog accepts --profile, see profiles.


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
