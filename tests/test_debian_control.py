"""debian/control's runtime Depends must carry the same version floors as
pyproject.toml. Debian and Ubuntu ship pydantic 1.x and internetarchive
<5.0 in every currently-supported release but trixie, so an unversioned
Depends lets apt install a pydantic-v1 stack that crashes dedb on the
first import (see debian-version-floors in RELEASE history) - apt
should refuse the install instead.
"""

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).parent.parent

# PyPI distribution name -> Debian binary package name, for the runtime
# deps that both files declare.
DEBIAN_PACKAGE = {
    "click": "python3-click",
    "pydantic": "python3-pydantic",
    "tomli": "python3-tomli",
    "internetarchive": "python3-internetarchive",
}


def _pyproject_floors() -> dict[str, str]:
    """{debian package: minimum version} from pyproject.toml's `>=` deps."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    floors = {}
    for dep in data["project"]["dependencies"]:
        name, sep, rest = dep.partition(">=")
        if not sep:
            continue
        name = name.strip()
        if name in DEBIAN_PACKAGE:
            floors[DEBIAN_PACKAGE[name]] = rest.split(";")[0].strip()
    return floors


def _debian_floors() -> dict[str, str]:
    """{debian package: minimum version} from debian/control's Depends."""
    control = (ROOT / "debian" / "control").read_text()
    depends = re.search(r"^Depends:(.*?)(?=^\S|\Z)", control, re.S | re.M)[1]
    return dict(re.findall(r"(python3-[\w.-]+)\s*\(>=\s*([\w.]+)\)", depends))


def test_debian_control_has_the_same_floors_as_pyproject():
    pyproject = _pyproject_floors()
    debian = _debian_floors()
    assert pyproject, "sanity check: pyproject.toml parsed no >= dependencies"
    for package, floor in pyproject.items():
        assert package in debian, f"debian/control has no version floor for {package}"
        assert debian[package] == floor, (
            f"debian/control's {package} floor is {debian[package]!r}, "
            f"pyproject.toml's is {floor!r}"
        )
