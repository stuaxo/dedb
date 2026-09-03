# GOG

GOG (Good Old Games) sells DOS games; the DOS ones usually run in DOSBox.
With a GOG account, dedb downloads a DOSBox-based GOG game and generates a
DOSEMU2 config for it. The conversion is described in
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Configuration

See the main README for `download_dir` and `[dosbox]`.

GOG DOSBox games need `dosbox-staging` - they don't run under plain
upstream `dosbox`. If it is on PATH the default `[dosbox]` setting picks
it up; otherwise set it:

```toml
[dosbox]
dosbox = "dosbox_staging"
```

## Commands

Name a game `gog:<gamename>`, then:

```
$ dedb download gog:tyrian_2000
$ dedb run gog:tyrian_2000 --dosbox            # the unaltered game - a baseline
$ dedb run gog:tyrian_2000 --dosemu
$ dedb run gog:tyrian_2000 --dosbox --cmdline  # print the emulator command, don't run it
$ dedb run 'gog:warcraft_orcs_and_humans?profile=server' --dosbox
$ dedb run tyrian_2000 -b gog --dosbox         # -b instead of the prefix
$ dedb import gog:tyrian_2000
$ dedb dosboxconf gog:tyrian_2000 --issues
$ dedb dosemuconf gog:tyrian_2000              # the converted dosemu.conf + userhook.bat
$ dedb rm gog:tyrian_2000
```

`dedb run --dosemu` converts the game on first use; `dedb import` does the
same without running it, and `dedb dosemuconf` shows the result without
writing it.

Two commands act on your whole GOG library rather than one game:

| Command | Does |
|---|---|
| `dedb lsgog` | List your GOG games. DOS games only unless `--all`; `-1` for bare lines. |
| `dedb downloadgog` | Download your GOG DOS games. `--all` for the DOS library, `--game <id>` for one. |

`dedb downloadgog --game tyrian_2000` and `dedb download gog:tyrian_2000`
do the same thing.

## Profiles

A GOG DOSBox game can ship several `dosbox*.conf` files - alternate launch
profiles (e.g. to add netplay), not pieces to merge. GOG records them in
`goggame-*.info` as `playTasks`; each conf-referencing playTask becomes a
profile. Non-DOSBox playTasks (GOG tools like `GOGDOSConfig.exe`) are
ignored.

Pick one with `gog:<id>?profile=<slug>` or `--profile <slug>`.

`warcraft_orcs_and_humans`, for example:

| Conf | Role |
|---|---|
| `dosbox_warcraft.conf` | base hardware settings |
| `dosbox_warcraft_single.conf` | single player - the primary profile |
| `dosbox_warcraft_client.conf` | IPX client |
| `dosbox_warcraft_server.conf` | IPX server |

## Directory structure

`<download_dir>/gog/<game_id>/`:

- `installer/` - the extracted GOG installer, deleted after extraction unless `--keep`
- `game/` - extracted install
- `metadata.json` - the shared metadata envelope (`dedb.core.metadata_file`); raw GOG metadata under `source`
- `dosemu/` - generated `dosemu.conf` / `userhook.bat`
