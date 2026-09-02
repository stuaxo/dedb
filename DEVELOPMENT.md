# Development

See [RELEASE.md](RELEASE.md) for the release process.
See [doc/backends.md](doc/backends.md) for how game-source backends
(`gog://`, `archive://`, ...) are registered and resolved.

## Checks

```bash
uv run ruff check .       # lint (config in pyproject.toml [tool.ruff])
uv run ruff format .      # autoformat
uv run pytest             # tests
```

Both run in CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
`ruff check` also runs as a [pre-commit](https://pre-commit.com) hook -
`pre-commit install` once to enable it.

## Local builds

To build the Debian package locally:

```bash
dpkg-buildpackage -us -uc
```
