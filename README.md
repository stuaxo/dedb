# dedb

DOSEMU2-DOSBOX importer and run games packaged for DOSBOX in DOSEMU2.


## Core commands

List available commands:
`$ dedb`

List downloaded programs:
`$ dedb ls`

List downloaded program URIs:

`$ dedb ls -l`

Each program has a URI based on where it was downloaded from and an id,
this is an example listing containing some owned GoG games and some games that
have been licensed freely and then downloaded from archive.org:

```
$ dedb ls -l
gog:bio_menace
gog:jazz_jackrabbit_collection
archive:MajorStryker
archive:msdos_Electro_Man_1992
```

Filter by backend (repeatable, or comma-separated):
`$ dedb ls --type=gog`
`$ dedb ls --type=gog,archive`


For more ls options:
`$ dedb ls --help`


### Naming a game

`dedb run`, `download`, `import` and `rm` take one GAME argument:

| GAME                                 | Is                                            |
|--------------------------------------|-----------------------------------------------|
| `gog:<gamename>`                     | a GOG game (the lgogdownloader gamename slug) |
| `gog:<gamename>?profile=<slug>`      | a GOG launch profile                          |
| `archive:<identifier>`               | an archive.org item                           |
| `https://archive.org/details/<name>` | an archive.org item, by URL                   |
| `<name>`                             | a downloaded game by name                     |

Examples:

```
$ dedb run gog:tyrian_2000 --dosbox
$ dedb run archive:msdos_Electro_Man_1992 --dosemu
$ dedb run 'gog:warcraft_orcs_and_humans?profile=server' --dosbox -- -fullscreen
$ dedb download gog:tyrian_2000
$ dedb rm gog:tyrian_2000
```


Slashes after the colon are ignored, the following are equivalent:
  `gog:x`, `gog://x` and `gog:///x`.

Names without backends can be used for games and programs that have already been
downloaded, unless they clash, in which case use a URI or specify a backend with
`-b`:

```
$ dedb run tyrian_2000 -b gog --profile server --dosbox
```

`-b <scheme>` with a bare id is `<scheme>://<id>`. `--profile` is `?profile=`.

To add a backend, see [doc/backends.md](doc/backends.md).


## Configuration

The dedb config file is `~/.config/dedb/dedbconf.toml`.

The main two things to configure are the `download_dir` and `dosbox`,
most programs work better in a patched `doxbox` rather than the default, e.g.
`dosbox-staging` or `dosbox-x` (note only dosbox-staging has been tested so far)

Example config:

```toml
# Directory to download programs and games.
# Backends get subdirectories off this e.g. 
# <download_dir>/gog/, <download_dir>/archive/, ...
download_dir = "/home/stu/dos/downloads"


[dosbox]
# Set the dosbox implementation used by `dedb run <game> --dosbox`.
# "default" First available dosbox-staging
# "dosbox"  Stock DOSBOX (not recommended)
# "dosbox_staging" DOSBOX-staging
# "dosbox_x" DOSBOX-testing (currently untested)
# "dosbox_pure" DOSBOX-pure (currently untested)
dosbox = "default"

[archive]
# archive.org screen name whose public favorites `dedb lsarchive` lists.
# Left unset, `lsarchive` prompts for it and offers to save it here.
favorites_user = "your-archive-org-username"
```


Developer config settings:
```toml
# Enable or disable apps that make up dedb (default is to include all):
# apps = ["dedb.dosbox", "dedb.gog", "dedb.archive"]
```


## Good Old Games (GOG)

If you have a GOG (Good Old Games) account you can download and run your games.

### Requirements:

GOG support requires `lgogdownloader` and `innoextract`, install them first:

On Debian / Ubuntu run:

`sudo apt install lgogdownloader innoextract`

When you first use a command that connects to GOG such as lsgog or download, you
will be prompted for your GOG sign-up email and password.


### List games

lsgog lists the games you own on GOG.

```sh
$ dedb lsgog
gog:bio_menace                                     local
gog:tyrian_2000                                    remote
```

### Download and run games

GOG games are specified using a URI scheme with `gog:` at the front, e.g.
`gog:<id>` or `gog:<id>?profile=<slug>`.

Download tyrian_2000:

```$ dedb download gog:tyrian_2000```

Run tyrian_2000 in dosemu:

```$ dedb run gog:tyrian_2000 --dosemu``` 

Run tyrian_2000 in dosbox:

```$ dedb run gog:tyrian_2000 --dosbox``` 


### Downloading in bulk

`downloadgog --all` downloads every owned game that looks DOSBox-based;
`downloadgog --game <id>` downloads just one.


### More information:

See `docs/gog.md` for more information on managing games from GOG.


## Archive.org

Games in archive.orgs DOS collection can be downloaded and run.

You can use their URL directly:

```$ dedb run https://archive.org/details/msdos_Electro_Man_1992```

These have a URI scheme that looks like ```archive:<id>```


You can also use:

```$ dedb run archive:msdos_Electro_Man_1992```

### List a user's favorites

`lsarchive` lists the public favorites of an archive.org user as
`archive:<id>` targets, filtered to MS-DOS items by default:

```sh
$ dedb lsarchive
archive:msdos_Commander_Keen_3_-_Keen_Must_Die_1990   Commander Keen 3 - Keen Must Die! (1990)
archive:msdos_Electro_Man_1992                        Electro Man (1992)
```

The username comes from the `[archive]` `favorites_user` setting; if
that isn't set you're prompted for it once and offered the chance to
save it. Pass `--user <name>` to list someone else, `--all` to include
non-DOS favorites, and `-1` for bare `archive:<id>` lines.
