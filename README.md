# de/db - DOSEMU/DOSBox interop tool

Import and run games packaged for DOSBox in DOSEMU2.

dedb is for testing DOSBox programs under DOSEMU2. As well as running the
games, it shows what each one needs to run, which surfaces
interoperability gaps.

It provides fixes and shims where it can, though ideally these stop being
needed over time as DOSEMU2 and its DOS utilities gain the features.


At its core dedb translates a game's `dosbox.conf` + `[autoexec]` into a
DOSEMU2 `dosemu.conf` + `userhook.bat`; see [ARCHITECTURE.md](ARCHITECTURE.md).


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
`$ dedb ls -b gog`
`$ dedb ls -b gog,archive`


For more ls options:
`$ dedb ls --help`


### Naming a game

`dedb run` takes one GAME; `download`, `import` and `rm` take any number
(`refreshmetadata` too, or none for every downloaded game):

| GAME                                 | Is                                            |
|--------------------------------------|-----------------------------------------------|
| `gog:<gamename>`                     | a GOG game (the lgogdownloader gamename slug) |
| `gog:<gamename>?profile=<slug>`      | a GOG launch profile                          |
| `archive:<identifier>`               | an archive.org item                           |
| `https://archive.org/details/<name>` | an archive.org item, by URL                   |
| `<name>`                             | a downloaded game by name                     |
| `<pattern>` (`rm` only)              | a `*`/`?`/`[]` wildcard over downloaded names (optionally `gog:<pattern>`) |
| `path/to/dosbox.conf` (`import` / `dosboxconf` / `dosemuconf` only) | a dosbox.conf on disk - several are merged; `import` writes the result to `-o`, the `*conf` commands print it |

Examples:

```
$ dedb run gog:tyrian_2000 --dosbox
$ dedb run archive:msdos_Electro_Man_1992 --dosemu
$ dedb run gog:tyrian_2000 --dosbox --cmdline   # print the command, don't run it
$ dedb run 'gog:warcraft_orcs_and_humans?profile=server' --dosbox -- -fullscreen
$ dedb download gog:tyrian_2000 gog:warcraft_orcs_and_humans
$ dedb rm gog:tyrian_2000
$ dedb rm 'gog:tyrian*' doom          # wildcards + names; one confirmation for the set
$ dedb refreshmetadata               # re-fetch metadata.json for every downloaded game
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


## Running a game

`dedb run GAME --dosbox` or `--dosemu` launches the game, downloading it -
and, for `--dosemu`, converting it - first if needed.

| Option | Effect |
|---|---|
| `--dosbox` / `--dosemu` | which emulator to run (one is required) |
| `--cmdline` | print the command that would run and stop; nothing is downloaded, converted or launched, and the game must already be downloaded |
| `-v`, `--verbose` | print the command line before launching |
| `--profile <slug>` | GOG launch profile (same as `gog:<id>?profile=<slug>`) |
| `-b`, `--backend <scheme>` | read GAME as a bare id for this backend |
| `--redownload` | re-download and re-extract even if already present |
| `-r`, `--refreshmetadata` | re-fetch cached backend metadata first |
| `--keep` | keep the installer/archive after extracting |

Anything after `--` is passed straight to the emulator:

```
$ dedb run gog:tyrian_2000 --dosbox -- -fullscreen
```


## Converting a game

The conversion turns a game's `dosbox.conf` + `[autoexec]` - or, for an
archive.org item, its launch command line - into a DOSEMU2 `dosemu.conf`
+ `userhook.bat`. See [ARCHITECTURE.md](ARCHITECTURE.md) for how it
works.

`dedb dosboxconf` inspects the DOSBox side before converting:

```
$ dedb dosboxconf gog:tyrian_2000            # [autoexec], Sound Blaster, Gravis
$ dedb dosboxconf gog:tyrian_2000 --issues   # what DOSEMU2 can't run as-is, by severity
$ dedb dosboxconf gog:tyrian_2000 --cmdline  # the dosbox command `run --dosbox` would use
```

`-a` / `-s` / `-g` narrow the default output to `[autoexec]`,
`[sblaster]` or `[gus]`; `-v` with `--issues` shows each autoexec line
and its rewrite. SOURCES can be `dosbox.conf` paths instead of a game.

`dedb dosemuconf` shows the converted output without writing it:

```
$ dedb dosemuconf gog:tyrian_2000            # dosemu.conf + userhook.bat
$ dedb dosemuconf gog:tyrian_2000 --conf     # just dosemu.conf
$ dedb dosemuconf gog:tyrian_2000 --userhook # just userhook.bat
$ dedb dosemuconf gog:tyrian_2000 --issues   # the same block as `dosboxconf --issues`
$ dedb dosemuconf gog:tyrian_2000 --cmdline  # the dosemu command `run --dosemu` would use
```

`dedb import` writes that output to disk. `dedb run --dosemu` does this
on first use; `import` does it without running:

```
$ dedb import gog:tyrian_2000                # into the download's dosemu/ dir
$ dedb import a.conf b.conf -o out/          # merge conf files (later wins) into out/
$ dedb import gog:tyrian_2000 --refreshconf  # regenerate for an already-converted game
```

`-f` / `--force` overwrites an existing output dir; `--refreshconf`
implies it.


## Shell completion

The Debian package installs tab completion for bash, zsh and fish. bash
also needs the `bash-completion` package (a recommended dependency).
Start a new shell to pick it up.

Completion covers commands and options, and completes a GAME argument to
`gog:<id>` / `archive:<id>` targets it can name from local data - games
you have downloaded, your GOG library (once `lsgog` has cached it) and
archive.org items dedb has already fetched metadata for. It never hits
the network.

For a pip install, print the script and put it where your shell reads
completions:

```sh
dedb completion bash | sudo tee /usr/share/bash-completion/completions/dedb
dedb completion zsh  | sudo tee /usr/share/zsh/vendor-completions/_dedb
dedb completion fish > ~/.config/fish/completions/dedb.fish
```

Without root, source the script from your shell's rc file instead:

```sh
dedb completion bash > ~/.dedb-complete.bash
echo 'source ~/.dedb-complete.bash' >> ~/.bashrc
```


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
download_dir = "~/dos/download_dir"


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
archive_user = "your-archive-org-username"
```


Developer config settings:
```toml
# Enable or disable apps that make up dedb (default is to include all):
# apps = ["dedb.dosbox", "dedb.dosemu", "dedb.gog", "dedb.archive"]
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

`dedb downloadgog --all` downloads every owned game that looks
DOSBox-based; `dedb downloadgog --game <id>` downloads just one.


### More information:

See [doc/gog.md](doc/gog.md) for more on managing GOG games.


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

The username comes from the `[archive]` `archive_user` setting; if
that isn't set you're prompted for it once and offered the chance to
save it. Pass `--user <name>` to list someone else, `--all` to include
non-DOS favorites, and `-1` for bare `archive:<id>` lines.

See [doc/archive.md](doc/archive.md) for more on archive.org.
