"""Tests for dedb.convert.models.

DosboxConfig mirrors dosbox.conf's own vocabulary; DosemuConfig mirrors
dosemu.conf's. DosemuConfigFromDosbox is the translation layer between
them, and dosbox_to_dosemu runs the pipeline.
"""

import pytest

from dedb.convert.models import (
    DosboxConfig,
    DosemuConfig,
    DosemuConfigFromDosbox,
    dosbox_to_dosemu,
)
from dedb.testing.model_naming import (
    assert_serialization_aliases_add_only_prefix,
    assert_validation_aliases_are_structural,
)

# DosboxConfig's validation_alias only locates a value in dosbox.conf;
# DosemuConfig's serialization_alias only adds the `$_` prefix. Neither
# renames - that's DosemuConfigFromDosbox's job.
LEFT_MODELS = [DosboxConfig]
RIGHT_MODELS = [(DosemuConfig, "$_")]


@pytest.mark.parametrize("model_cls", LEFT_MODELS)
def test_left_model_aliases_only_locate_never_rename(model_cls):
    assert_validation_aliases_are_structural(model_cls)


@pytest.mark.parametrize(("model_cls", "prefix"), RIGHT_MODELS)
def test_right_model_aliases_only_add_the_prefix(model_cls, prefix):
    assert_serialization_aliases_add_only_prefix(model_cls, prefix)


def test_config_keys_by_section_has_one_entry_per_section_mapped_field():
    by_section = DosboxConfig.config_keys_by_section()

    field_names = [name for keys in by_section.values() for name in keys.values()]
    # `autoexec` is a verbatim list, not a section/key value, so it has no
    # AliasPath and is not part of this map.
    assert sorted(field_names) == sorted(n for n in DosboxConfig.model_fields if n != "autoexec")


def test_config_keys_by_section_maps_a_section_key_pair_to_its_field_name():
    by_section = DosboxConfig.config_keys_by_section()

    assert by_section["sdl"]["fullscreen"] == "fullscreen"
    assert by_section["cpu"]["cycles"] == "cycles"
    assert by_section["dosbox"]["memsize"] == "memsize"


def test_autoexec_defaults_to_empty_and_is_populated_by_name():
    assert DosboxConfig().autoexec == []
    assert DosboxConfig.model_validate({"autoexec": ["c:", "GAME.EXE"]}).autoexec == [
        "c:",
        "GAME.EXE",
    ]


def test_get_mounts_resolves_the_autoexec_mounts_against_a_working_dir(tmp_path):
    config = DosboxConfig(autoexec=["MOUNT D SAVES", "IMGMOUNT E disk.img", "GAME.EXE"])

    mounts = config.get_mounts(tmp_path)

    assert [(m.dos_drive, m.dos_path) for m in mounts] == [("D", "SAVES")]
    assert mounts[0].host_path == (tmp_path / "SAVES").resolve()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("TRUE", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_bool_string_coercion_for_multiple_fields(raw: str, expected: bool):
    config = DosboxConfig.model_validate(
        {
            "sdl": {"fullscreen": raw},
            "gus": {"gus": raw},
            "speaker": {"pcspeaker": raw},
        }
    )

    assert config.fullscreen is expected
    assert config.gus is expected
    assert config.pcspeaker is expected


@pytest.mark.parametrize(
    ("field", "dosbox_default"),
    [("fullscreen", False), ("cycles", "auto"), ("memsize", 16), ("sbtype", "sb16")],
)
def test_absent_fields_take_dosbox_own_default(field: str, dosbox_default):
    assert getattr(DosboxConfig.model_validate({}), field) == dosbox_default


def test_cycles_is_kept_as_dosbox_wrote_it():
    """cycles is DOSBox's own free-form value ("max", "auto", "max 80%",
    "fixed 3000"...); DosboxConfig stores it verbatim and leaves
    interpreting it to the translation model."""
    config = DosboxConfig.model_validate({"cpu": {"cycles": "fixed 3000"}})

    assert config.cycles == "fixed 3000"


@pytest.mark.parametrize(
    ("memsize", "expected"),
    [
        ("16", 16),
        ("256", 256),
        ("not-a-number", 16),
    ],
)
def test_memsize_string_coercion(memsize: str, expected: int):
    config = DosboxConfig.model_validate({"dosbox": {"memsize": memsize}})

    assert config.memsize == expected


@pytest.mark.parametrize(
    ("cycles", "expected_cpuspeed"),
    [
        ("max", 0),
        ("auto", 0),
        ("max 80%", 0),
        ("3000", 3000),
        ("  4000  ", 4000),
    ],
)
def test_dosbox_to_dosemu_reads_cycles_as_cpuspeed(cycles: str, expected_cpuspeed: int):
    target = dosbox_to_dosemu(DosboxConfig(cycles=cycles))

    assert target.cpuspeed == expected_cpuspeed


def test_dosbox_to_dosemu_does_not_read_fixed_cycles_as_a_speed():
    """DOSBox's "cycles=fixed N" and "cycles=N" set the same behaviour,
    but only the bare form is read as a speed here: the "fixed" token is
    not stripped, so int() fails and cpuspeed falls back to 0 (auto).
    This locks in the current behaviour; it is a candidate for a
    follow-up fix rather than something this test asserts is correct."""
    target = dosbox_to_dosemu(DosboxConfig(cycles="fixed 3000"))

    assert target.cpuspeed == 0


@pytest.mark.parametrize(
    ("memsize", "expected_dpmi_kb"),
    [
        (16, 131072),  # below the floor: floored to 128Mb, then converted
        (128, 131072),  # exactly the floor
        (129, 132096),  # above the floor: converted, not floored
        (256, 262144),
    ],
)
def test_dosbox_to_dosemu_floors_then_converts_memsize_to_dpmi(memsize: int, expected_dpmi_kb: int):
    target = dosbox_to_dosemu(DosboxConfig(memsize=memsize))

    assert target.dpmi == expected_dpmi_kb


def test_dosbox_to_dosemu_translates_the_remaining_fields():
    target = dosbox_to_dosemu(
        DosboxConfig(fullscreen=True, pcspeaker=True, serial1="dummy", joysticktype="none")
    )

    assert target.X_fullscreen is True  # renamed, copied unchanged
    assert target.speaker == "emulated"
    assert target.com1 == ""
    assert target.joystick == ""

    target_alt = dosbox_to_dosemu(
        DosboxConfig(pcspeaker=False, serial1="directserial", joysticktype="auto")
    )

    assert target_alt.speaker == ""
    assert target_alt.com1 == ""  # always empty for now
    assert target_alt.joystick == "/dev/input/js0"


def test_dosbox_to_dosemu_does_not_emit_video():
    """DOSBox's `output` is a host rendering-surface choice with no
    dosemu2 equivalent, so it is not translated and $_video is left out
    of the rendered conf entirely (dosemu2 defaults it to "vga")."""
    assert not hasattr(dosbox_to_dosemu(DosboxConfig(output="opengl")), "video")


def test_translation_model_reads_dosbox_field_names_and_converts():
    """DosemuConfigFromDosbox reads a DosboxConfig dump: its aliases are
    DosboxConfig field names, its validators do the conversion."""
    mid = DosemuConfigFromDosbox.model_validate(
        DosboxConfig(cycles="4000", memsize=8, mpu401="none").model_dump()
    )

    assert mid.cpuspeed == 4000
    assert mid.dpmi == 131072  # 8 -> floored to 128 MB -> KB
    assert mid.mpu401_base == 0 and mid.mpu401_irq == 0


def test_translation_model_drops_unsupported_fields_from_the_dump():
    mid = DosemuConfigFromDosbox.model_validate(DosboxConfig(output="opengl").model_dump())

    assert "output" not in mid.model_dump()
    assert set(mid.model_dump()) == set(DosemuConfig.model_fields)


@pytest.fixture
def dosemu():
    """A fully-populated DosemuConfig - the translated DOSBox defaults."""
    return dosbox_to_dosemu(DosboxConfig())


@pytest.mark.parametrize(("fullscreen", "rendered"), [(True, "on"), (False, "off")])
def test_model_dump_dosemurc_renders_fullscreen_as_on_off(fullscreen, rendered, dosemu):
    output = dosemu.model_copy(update={"X_fullscreen": fullscreen}).model_dump_dosemurc()

    assert f"$_X_fullscreen = ({rendered})" in output.splitlines()


def test_model_dump_dosemurc_renders_dpmi_without_further_conversion(dosemu):
    """dpmi is already in DOSEMU2's units by the time it reaches
    DosemuConfig; model_dump_dosemurc must not scale it again."""
    output = dosemu.model_copy(update={"dpmi": 262144}).model_dump_dosemurc()

    assert "$_dpmi = (262144)" in output.splitlines()


def test_model_dump_dosemurc_full_output(dosemu):
    output = dosemu.model_copy(
        update={"X_fullscreen": True, "cpuspeed": 3000, "dpmi": 131072}
    ).model_dump_dosemurc()

    assert "$_X_fullscreen = (on)" in output.splitlines()
    assert "$_cpuspeed = (3000)" in output.splitlines()
    assert "$_dpmi = (131072)" in output.splitlines()
