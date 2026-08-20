# GOG

Each game lives at `<gog.download_dir>/<game_id>/`:

- `installer/` — deleted after conversion unless `--keep`
- `game/` — extracted install
- `metadata.json` — cached GOG metadata and launch profiles
- `dosemu/` — generated `dosemu.conf`/`userhook.bat`

## Launch profiles

A GOG DOSBox game can ship more than one `dosbox*.conf`. These are usually
alternate launch modes, not files to merge.

`goggame-*.info` lists each mode as a `playTask`, one marked primary. A
task counts as a profile if it references at least one `-conf` file. Tasks
that don't — tools like `GOGDOSConfig.exe` — are ignored.

`importgog` converts every profile by default: the primary profile writes
`dosemu.conf`/`userhook.bat`, each other profile writes its own
`dosemu_<profile>.conf`/`userhook_<profile>.bat`, generated from that
profile's own confs and autoexec. `importgog`/`rungog --profile
<name-or-slug>` selects a single profile.

Games without a usable `goggame-*.info` fall back to merging every
`dosbox*.conf` found — the old behaviour, still correct for a single conf
or a base conf plus a genuine merge-in variant.

### Example: warcraft_orcs_and_humans

| Conf | Role |
|---|---|
| `dosbox_warcraft.conf` | Base hardware settings |
| `dosbox_warcraft_single.conf` | Single player — the primary profile |
| `dosbox_warcraft_client.conf` | IPX client |
| `dosbox_warcraft_server.conf` | IPX server |

The client and server confs aren't referenced by any `playTask`. GOG
launches multiplayer through a separate bundled tool,
`GOGDOSConfig.exe <product_id> NET`, which picks the conf itself. `dedb`
can't read that choice, so these two confs aren't reachable via `--profile`
for this game.
