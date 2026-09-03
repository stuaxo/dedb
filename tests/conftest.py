"""Shared fixtures for the dedb test suite.

The conf and autoexec text here is modelled on the shape of real GOG
DOS releases (a base hardware profile plus a variant profile, and a
choice-driven launcher batch), but no game, company or product name
from those releases appears anywhere in this file. Use these fixtures,
or extend them, instead of copying text from a downloaded game.
"""

import tempfile
from pathlib import Path

import pytest

# Isolate the whole session from the real ~/.config/dedb *before* any test
# module imports dedb.cli - it registers app commands from Settings.apps at
# import time, so a stale pinned `apps` in the user's config would other-
# wise decide which commands exist during the run. Points at an empty dir,
# so load_settings() falls back to the packaged default (every app).
_SESSION_CFG = Path(tempfile.mkdtemp(prefix="dedb-test-cfg-"))
from dedb.core import settings as _settings  # noqa: E402

_settings.CONFIG_DIR = _SESSION_CFG
_settings.SETTINGS_PATH = _SESSION_CFG / "dedbconf.toml"


@pytest.fixture(autouse=True)
def _isolate_dedb_config(tmp_path_factory, monkeypatch):
    """Point settings at a throwaway config dir and clear the cache, so the
    suite never reads or writes the real ~/.config/dedb (load_settings now
    creates the file on first run)."""
    from dedb.core import settings

    cfg_dir = tmp_path_factory.mktemp("dedbconf")
    settings_path = cfg_dir / "dedbconf.toml"
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(settings, "SETTINGS_PATH", settings_path)
    settings.get_settings.cache_clear()  # real lru_cache here; tests patch it later
    yield


@pytest.fixture
def base_profile_conf() -> str:
    """A base hardware profile, standing in for a game's primary
    dosbox*.conf."""
    return """
[sdl]
fullscreen=false
output=surface

[dosbox]
memsize=16

[cpu]
cycles=auto

[autoexec]
MOUNT C GAME
game.exe
"""


@pytest.fixture
def variant_profile_conf() -> str:
    """A second profile that overrides a subset of the base profile's
    settings, standing in for a GOG game's alternate launch profile
    (e.g. a "single player" or higher-spec variant)."""
    return """
[sdl]
fullscreen=true

[cpu]
cycles=max

[autoexec]
setup.exe
"""


LAUNCHER_AUTOEXEC_LINES = [
    "@ECHO OFF",
    'MOUNT C ".."',
    'MOUNT D "..\\cloud_saves" -t overlay',
    "c:",
    "CHOICE /C123 /S Which program do you want to run?: /N",
    "if errorlevel 3 goto exit",
    "if errorlevel 2 goto edit",
    "if errorlevel 1 goto game",
    ":game",
    "GAME.EXE",
    "goto exit",
    ":edit",
    "EDITOR.EXE",
    ":exit",
    "exit",
]


@pytest.fixture
def launcher_autoexec_lines() -> list[str]:
    """Autoexec commands for a choice-driven launcher batch, standing in
    for the menu script GOG installers commonly generate to pick between
    a game, its editor and its setup utility."""
    return list(LAUNCHER_AUTOEXEC_LINES)


@pytest.fixture
def launcher_profile_conf() -> str:
    """A full profile - hardware settings plus the launcher batch above -
    standing in for a game's primary dosbox*.conf."""
    autoexec_block = "\n".join(LAUNCHER_AUTOEXEC_LINES)
    return f"""
[sdl]
fullscreen=false

[dosbox]
memsize=16

[cpu]
cycles=auto

[autoexec]
{autoexec_block}
"""


@pytest.fixture
def write_conf(tmp_path: Path):
    """Write text to a numbered .conf file under tmp_path and return its
    path. Repeated calls in one test produce distinct files."""
    counter = iter(range(1000))

    def _write(text: str) -> Path:
        path = tmp_path / f"dosbox{next(counter)}.conf"
        path.write_text(text, encoding="cp437")
        return path

    return _write
