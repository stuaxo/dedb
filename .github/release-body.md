## Downloads

| File | What it is | Install |
| --- | --- | --- |
| `dedb-<version>-py3-none-any.whl` | Python wheel, all platforms | `pipx install <url>` / `uv tool install <url>` / `pip install <url>` |
| `dedb-<version>.tar.gz` | Python source distribution (sdist) | same as the wheel; builds from source |
| `python3-dedb_<version>_all.deb` | Debian / Ubuntu package | `sudo apt install ./python3-dedb_<version>_all.deb` |

`<url>` is the download link for the file listed under **Assets** below.

Install without downloading first (any tag, branch, or commit):

    pipx install "git+https://github.com/stuaxo/dedb.git@<tag>"
