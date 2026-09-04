## Installation

### Python package (pip / uv / pipx)

Any OS with Python 3.10+.

`pipx install` or `uv tool install` are convenient ways to install dedb:

```
pipx install https://github.com/stuaxo/dedb/releases/download/@REF@/dedb-@VERSION@-py3-none-any.whl
```

`pip install` works too, into an existing virtual environment. The
`.tar.gz` source distribution installs the same way as the wheel.

### Debian / Ubuntu package

Needs **Debian 13 (trixie) or later**, or **Ubuntu 26.04 LTS or later**.

```
sudo apt install ./python3-dedb_@VERSION@_all.deb
```

dedb depends on pydantic 2 and internetarchive 5; no earlier Debian or
Ubuntu release packages both new enough. On an older release, or
another distro, use the Python package above instead.
