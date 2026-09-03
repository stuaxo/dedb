# Development

See [ARCHITECTURE.md](ARCHITECTURE.md) for the shape of the codebase -
the DOSBox->DOSEMU2 conversion at its core and what sits around it.
See [RELEASE.md](RELEASE.md) for the release process.
See [doc/backends.md](doc/backends.md) for how game-source backends
(`gog://`, `archive://`, ...) are registered and resolved.

## Checks

```bash
uv run ruff check .       # lint (config in pyproject.toml [tool.ruff])
uv run ruff format .      # autoformat
uv run pytest             # tests
```

After changing `dedb.dosbox.models.TRANSLATIONS` (the DOSBox->DOSEMU2
field map), refresh the table in ARCHITECTURE.md:

```bash
uv run python -m dedb.dosbox.fieldmap --write
```

`test_fieldmap.py` fails until you do.

Both run in CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
`ruff check` also runs as a [pre-commit](https://pre-commit.com) hook -
`pre-commit install` once to enable it.

## Shell completion

`completions/dedb.{bash,zsh,fish}` are click's own completion output,
installed by the Debian package (debian/python3-dedb.install).
Regenerate them after a click upgrade or a change to the root command
name:

```bash
uv run python completions/_generate.py
```

`test_completion.py` fails until you do.

## Local builds

To build the Debian package locally:

```bash
dpkg-buildpackage -us -uc
```
