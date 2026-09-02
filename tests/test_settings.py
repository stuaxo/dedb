"""Tests for dedb.core.settings.load_settings.

The autouse _isolate_dedb_config fixture (conftest) already points
settings.SETTINGS_PATH / CONFIG_DIR at a throwaway dir, so these just
call load_settings() and inspect the result and the file it writes.
Reach SETTINGS_PATH through the module - the fixture patches it there.
"""

import pytest

from dedb.core import settings
from dedb.core.settings import (
    DosboxSettings,
    Settings,
    load_settings,
    save_archive_favorites_user,
)


def test_missing_file_is_created_from_the_packaged_default():
    assert not settings.SETTINGS_PATH.exists()

    result = load_settings()

    assert settings.SETTINGS_PATH.read_text() == settings.default_settings_text()
    assert result == Settings()  # built-in defaults


def test_the_written_default_leaves_download_dir_commented_out():
    load_settings()
    text = settings.SETTINGS_PATH.read_text()

    assert "# download_dir" in text
    assert not any(line.strip().startswith("download_dir") for line in text.splitlines())
    assert load_settings().download_dir is None


def test_invalid_toml_falls_back_to_defaults_with_a_warning(capsys):
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text("this = is not = valid toml")

    result = load_settings()

    assert result == Settings()
    assert "ignoring invalid" in capsys.readouterr().err


def test_invalid_schema_falls_back_to_defaults_with_a_warning(capsys):
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text('apps = "not-a-list"\n')

    result = load_settings()

    assert result == Settings()
    assert "ignoring invalid" in capsys.readouterr().err


def test_a_bad_dosbox_choice_falls_back_to_defaults_with_a_warning(capsys):
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text('[dosbox]\ndosbox = "dosbox-x"\n')  # hyphen, not underscore

    result = load_settings()

    assert result == Settings()
    assert "ignoring invalid" in capsys.readouterr().err


# --- DosboxSettings.get_dosbox_binary(): choice -> executable name -----


def test_get_dosbox_binary_maps_an_explicit_choice_straight_through():
    assert DosboxSettings(dosbox="dosbox_x").get_dosbox_binary() == "dosbox-x"


def test_get_dosbox_binary_default_probes_path_in_order(monkeypatch):
    seen = []

    def fake_which(name):
        seen.append(name)
        return name if name == "dosbox" else None  # only plain dosbox installed

    monkeypatch.setattr(settings.shutil, "which", fake_which)
    assert DosboxSettings().get_dosbox_binary() == "dosbox"
    assert seen == ["dosbox-staging", "dosbox"]  # staging tried first


def test_get_dosbox_binary_default_falls_back_to_dosbox_when_nothing_is_installed(monkeypatch):
    monkeypatch.setattr(settings.shutil, "which", lambda _name: None)
    assert DosboxSettings().get_dosbox_binary() == "dosbox"  # so FileNotFoundError names it


def test_an_unknown_dosbox_choice_is_rejected_at_validation():
    with pytest.raises(ValueError, match="must be one of"):
        DosboxSettings(dosbox="nope")


# --- Settings.app_paths / .download_dir_for ---------------------------


def test_app_paths_prepends_the_builtin_and_dedupes_it():
    assert Settings().app_paths() == ["dedb.dedb", "dedb.dosbox", "dedb.gog", "dedb.archive"]
    # a config that names dedb.dedb explicitly doesn't get it twice, order kept
    assert Settings(apps=["dedb.gog", "dedb.dedb"]).app_paths() == ["dedb.dedb", "dedb.gog"]


def test_download_dir_for_namespaces_by_scheme_or_is_none(tmp_path):
    assert Settings(download_dir=None).download_dir_for("gog") is None
    assert Settings(download_dir=tmp_path).download_dir_for("gog") == tmp_path / "gog"


def test_a_valid_file_is_respected(tmp_path):
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text(
        f'download_dir = "{tmp_path}"\n[dosbox]\ndosbox = "dosbox_x"\n'
    )

    result = load_settings()

    assert result.download_dir == tmp_path
    assert result.dosbox.dosbox == "dosbox_x"


def test_archive_favorites_user_defaults_to_none_and_is_read_when_set():
    assert load_settings().archive.favorites_user is None

    settings.SETTINGS_PATH.write_text('[archive]\nfavorites_user = "someone"\n')
    assert load_settings().archive.favorites_user == "someone"


def test_save_archive_favorites_user_is_idempotent_and_preserves_comments():
    load_settings()  # write the packaged default, comments and all
    save_archive_favorites_user("first")
    save_archive_favorites_user("second")

    text = settings.SETTINGS_PATH.read_text()
    written = [ln for ln in text.splitlines() if ln.strip().startswith("favorites_user")]
    assert written == ['favorites_user = "second"']  # replaced, not appended
    assert "# dedb configuration." in text  # packaged comments survived
    assert load_settings().archive.favorites_user == "second"


def test_download_dir_expands_a_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text('download_dir = "~/downloads"\n')

    result = load_settings()

    assert result.download_dir == tmp_path / "downloads"


def test_download_dir_expands_env_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("DEDB_TEST_ROOT", str(tmp_path))
    settings.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text('download_dir = "$DEDB_TEST_ROOT/downloads"\n')

    result = load_settings()

    assert result.download_dir == tmp_path / "downloads"


def test_an_unwritable_config_dir_does_not_raise(capsys, monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    monkeypatch.setattr(settings, "CONFIG_DIR", blocker / "dedb")
    monkeypatch.setattr(settings, "SETTINGS_PATH", blocker / "dedb" / "dedbconf.toml")

    result = load_settings()  # must not raise

    assert result == Settings()
    assert "could not create" in capsys.readouterr().err
