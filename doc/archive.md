# Use archive.org DOS programs and games

dedb can download and run MS-DOS programs and games from archive.org as long as they have been setup for emulation there and
download is enabled.

If you have a login on archive.org then you can favorite programs and games there and list and download them from dedb.


## Identify a game

Programs and games on archive can be refered to by their identifier or URI:

* `archive:<identifier>`
* `archive://<identifier>`
* `[https://archive.org/details/](https://archive.org/details/)<identifier>`


## Configure dedb

The download directory must be configured in `~/.config/dedb/dedb.conf`.
Archive downloads are saved to `<download_dir>/archive/`.

```ini
download_dir = "/path/to/downloads"

```

### Set your username

If `archive_user` is set in the config when you run `lsarchive --favorites` it will default to this users favorites.
This allows you to setup your own list of items for testing within on Archive.org itself.

```ini
[archive]
archive_user = "your-archive-org-username"

```

You will be prompted for this the first time you run `dedb lsarchive` without a `--user` parameter.


## Manage and run games

Use the following commands to manage games. Replace `<id>` with the game identifier or URL.

* **Download a game:** `dedb download archive://<id>`
* **Run in DOSBox:** `dedb run archive://<id> --dosbox`
* **Run in DOSEMU2:** `dedb run archive://<id> --dosemu`
* **Import a game:** `dedb import archive://<id>`
* **Remove a game:** `dedb rm archive://<id>`

If you run a game that you have not downloaded, `dedb run` will automatically download and extract it first.

You can also use the `-b archive` flag instead of the `archive://` prefix (for example: `dedb run <id> -b archive --dosbox`).

## Find favourite games

You can list an archive.org user’s public favourites.
By default, this queries the public API and filters the results to only show MS-DOS games.

* **List your configured user's favourites:** `dedb lsarchive`
* **List another user's favourites:** `dedb lsarchive --user <username>`
* **Include non-DOS favourites:** `dedb lsarchive --all`
* **Output bare identifiers for scripts:** `dedb lsarchive -1`

You can pass the output of these commands directly into `dedb download` or `dedb run`.


## Technical details

### File structure

Games are stored in `<download_dir>/archive/<identifier>/`. This directory contains:

* `download/` - the downloaded `.zip` file (deleted automatically after extraction unless you run with `--keep`)
* `game/` - the extracted game files
* `metadata.json` - standard dedb metadata (raw archive.org metadata is stored in the `source` field)
* `dosemu/` - generated DOSEMU2 configuration files (`dosemu.conf` and `userhook.bat`)

### How games run in DOSBox

dedb reads the archive.org metadata to run the game. It requires:

* `emulator` set to `dosbox`
* `emulator_ext` set to `zip`
* `emulator_start` containing the path to the executable


Games on archive.org use a dosbox based emulator, but do not usually have a dosbox.conf instead metadata holds parameters passed on the
commandline (including the `autoexec` commands).


### Notes on how emularity works

On Archive.org the set of emulators ported to the web is collectively refered to sa "the emularity".
DOSBox based games and programs used a build of DOSBOX.

A program or game there is an "item" the relevant fields are:

* `emulator` - For DOS apps it will be `dosbox`.
* `emulator_ext` - extension of archive to download (.zip is supported.)
* `emulator_start` — path of the executable for the emulator to run (e.g. `ElectroM/EM.EXE`)
