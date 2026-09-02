# GOG

GOG (Good Old Games) have DOS based games in their catelogue, these
usually run in DOSBOX.

If you have a GOG account the tools here can download a DOSBOX based
game from GOG and generate a DOSEMU2 conf and related files for testing
vs DOSBOX.

For more information on the conversion process see `dosbox_to_dosemu.md`.


## Configuration

See the main README for `download_dir` and `[dosbox]` setup.

GOG DOSBox games need at least `dosbox-staging` - they don't run under
plain upstream `dosbox`. If `dosbox-staging` is on PATH the default
`[dosbox]` setting already picks it up; otherwise set it explicitly:

```toml
[dosbox]
dosbox = "dosbox_staging"
```


## Commands

Name a GOG game `gog:///<gamename>` (see the main README), then:

```
$ dedb download gog:///tyrian_2000
$ dedb run gog:///tyrian_2000 --dosbox
$ dedb run 'gog:///warcraft_orcs_and_humans?profile=server' --dosbox
$ dedb run tyrian_2000 -b gog --dosbox      # -b instead of the prefix
$ dedb import gog:///tyrian_2000
$ dedb dosboxconf gog:///tyrian_2000 --issues
$ dedb rm gog:///tyrian_2000
```

GOG-specific commands act on your GOG library, not a single game:

| Command       | Does                                                   |
|---------------|--------------------------------------------------------|
| `lsgog`       | List your DOS games on GOG.                            |
| `downloadgog` | Download your GOG DOS games. `--all` for the whole DOS library, `--game <id>` for one. |


### lsgog

List your GOG games, by default filters for DOS games use `--all` to show
every game.

Compact listing:

`lsgog -1`


### downloadgog

Download every owned game that looks DOSBox-based:

```$ downloadgog --all```

Or download a single game:

```$ downloadgog --game tyrian_2000```

(`dedb download gog:///tyrian_2000` does the same for one game.)

On initial download, a DOSEMU2 conf isn't created; `dedb import gog:///<id>` can
do this, and `dedb run` also does it on demand.



# Run GOG game in DOSBOX

```$ dedb run gog:///tyrian_2000 --dosbox```

This is a good baseline as this runs the unaltered game.


# Run GOG game in DOSEMU2

```$ dedb run gog:///tyrian_2000 --dosemu```

Pick a launch profile with `gog:///<id>?profile=<slug>` or `--profile <slug>` -
see profiles below.


## Profiles

GOG DOSBOX based games can multiple `dosbox*.conf` files, these are
alternate launch modes (e.g. to add netplay).

GOG stores metadata in `goggame-*.info` files,, these contain "modes" and each has
a `playTask`.

Some playTasks are launch parameters for DOSBOX, from these we create launch profiles.
Non DOSBOX modes are for GOG specific tools such as `GOGDOSConfig.exe` which we ignore.


### Example Profile: warcraft_orcs_and_humans

| Conf | Role |
|---|---|
| `dosbox_warcraft.conf` | Base hardware settings |
| `dosbox_warcraft_single.conf` | Single player — the primary profile |
| `dosbox_warcraft_client.conf` | IPX client |
| `dosbox_warcraft_server.conf` | IPX server |


## Directory structure
Games are downloaded to `<download_dir>/gog/<game_id>/`:

- `installer/` — deleted after conversion unless `--keep`
- `game/` — extracted install
- `metadata.json` — the shared metadata envelope (`dedb.core.metadata_file`): identity,
  classification and launch modes at the top level, the raw GOG metadata (profiles included)
  under `source`
- `dosemu/` — generated `dosemu.conf`/`userhook.bat`
