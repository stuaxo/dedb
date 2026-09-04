## Installation

### Python package (pip / uv / pipx)

Works on any OS with Python 3.10+.

```
pipx install https://github.com/stuaxo/dedb/releases/download/@REF@/dedb-@VERSION@-py3-none-any.whl
```

`uv tool install` takes the same URL. Use `pip install` for an install into
an existing virtual environment. The `.tar.gz` source distribution installs
the same way as the wheel.

### Debian / Ubuntu package

Needs **Debian 13 (trixie) or later**, or **Ubuntu 26.04 LTS or later** -
dedb requires pydantic 2 and internetarchive 5, and no earlier Debian or
Ubuntu release packages both new enough. On an older release, or another
distro, use the Python package above instead.

```
sudo apt install ./python3-dedb_@VERSION@_all.deb
```
