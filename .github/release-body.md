## Installation

### Python package (pip / uv / pipx)

Any OS with Python 3.10+.

`pipx install` or `uv tool install` are convenient ways to install dedb:

```
pipx install https://github.com/stuaxo/dedb/releases/download/@REF@/dedb-@VERSION@-py3-none-any.whl
```

`pip install` works too, into an existing virtual environment.

### Debian / Ubuntu package

**Debian 13 (trixie) or later**, or **Ubuntu 26.04 LTS or later** are
required, as dedb heavily relies on Pydantic 2 which isn't packaged
for earlier versions.

On earlier versions use the python package.

```
sudo apt install ./python3-dedb_@VERSION@_all.deb
```
