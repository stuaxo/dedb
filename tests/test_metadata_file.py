"""Tests for dedb.core.metadata_file.GameMetadataFile - the metadata.json
envelope and its v1 -> v2 upgrade.

The v1 fixtures under tests/fixtures/metadata/ are shaped exactly like the
files the pre-envelope code wrote (a single {"gog": {...}} / {"archive":
{...}} key), but carry no real game, company or product name.
"""

from pathlib import Path

import pytest

from dedb.core.metadata_file import CURRENT_SCHEMA, GameMetadataFile

FIXTURES = Path(__file__).parent / "fixtures" / "metadata"


def _copy(fixture: str, tmp_path: Path) -> Path:
    dest = tmp_path / "metadata.json"
    dest.write_text((FIXTURES / fixture).read_text())
    return dest


# --- v1 upgrade ------------------------------------------------------------


def test_reads_a_v1_gog_file_lifting_common_fields_and_keeping_the_blob(tmp_path):
    envelope = GameMetadataFile.read(_copy("gog_v1.json", tmp_path))

    assert envelope.schema_version == CURRENT_SCHEMA
    assert envelope.scheme == "gog"
    assert envelope.identifier == "sample_dos_game"
    assert envelope.classification == "dosbox"
    assert envelope.downloaded_at is not None  # from the blob's fetched_at
    # launch_profiles stay empty on a migrated file - the backend re-derives
    # them from the extracted goggame-*.info.
    assert envelope.launch_profiles == []
    # the whole v1 blob is preserved untouched under source
    assert envelope.source["product_id"] == "1234567890"
    assert [p["name"] for p in envelope.source["profiles"]] == ["Play", "Multiplayer Host"]


def test_reads_a_v1_archive_file(tmp_path):
    envelope = GameMetadataFile.read(_copy("archive_v1.json", tmp_path))

    assert envelope.scheme == "archive"
    assert envelope.identifier == "msdos_Sample_Game_1991"
    assert envelope.title == "Sample Game (1991)"
    assert envelope.year == "1991"
    assert envelope.source["emulator_start"] == "SAMPLE/GAME.EXE"


# --- v2 round-trip -------------------------------------------------------


def test_a_v2_file_round_trips_unchanged(tmp_path):
    original = GameMetadataFile(
        scheme="archive",
        identifier="msdos_X",
        title="X",
        classification="dosbox",
        source={"emulator": "dosbox", "emulator_start": "X.EXE"},
    )
    path = tmp_path / "metadata.json"
    path.write_text(original.model_dump_json(indent=2))

    assert GameMetadataFile.read(path) == original


def test_read_or_none_swallows_a_missing_or_broken_file(tmp_path):
    assert GameMetadataFile.read_or_none(tmp_path / "nope.json") is None

    broken = tmp_path / "metadata.json"
    broken.write_text("{not json")
    assert GameMetadataFile.read_or_none(broken) is None


def test_read_raises_on_a_broken_file(tmp_path):
    broken = tmp_path / "metadata.json"
    broken.write_text("{not json")
    with pytest.raises(ValueError):
        GameMetadataFile.read(broken)
