"""Tests for dedb.convert.models.

DosboxConfig mirrors dosbox.conf's own vocabulary; DosemuConfig mirrors
dosemu.conf's. dosbox_to_dosemu is the only place field names and units
cross from one side to the other.
"""

import pytest

from dedb.convert.models import DosboxConfig, DosemuConfig, dosbox_to_dosemu
from dedb.testing.model_naming import (
    assert_serialization_aliases_add_only_prefix,
    assert_validation_aliases_are_structural,
)

# Every left/right model pair this app translates between. A left model's
# validation_alias only locates a value in its source format; a right
# model's serialization_alias only adds its target format's prefix.
# Add a pair here when a new translation is added, rather than writing a
# one-off naming test for it.
LEFT_MODELS = [DosboxConfig]
RIGHT_MODELS = [(DosemuConfig, "$_")]


@pytest.mark.parametrize("model_cls", LEFT_MODELS)
def test_left_model_aliases_only_locate_never_rename(model_cls):
    assert_validation_aliases_are_structural(model_cls)


@pytest.mark.parametrize(("model_cls", "prefix"), RIGHT_MODELS)
def test_right_model_aliases_only_add_the_prefix(model_cls, prefix):
    assert_serialization_aliases_add_only_prefix(model_cls, prefix)


def test_config_keys_by_section_has_one_entry_per_field():
    by_section = DosboxConfig.config_keys_by_section()

    field_names = [name for keys in by_section.values() for name in keys.values()]
    assert sorted(field_names) == sorted(DosboxConfig.model_fields)


def test_config_keys_by_section_maps_a_section_key_pair_to_its_field_name():
    by_section = DosboxConfig.config_keys_by_section()

    assert by_section["sdl"]["fullscreen"] == "fullscreen"
    assert by_section["cpu"]["cycles"] == "cycles"
    assert by_section["dosbox"]["memsize"] == "memsize"


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


def test_fullscreen_defaults_to_false_when_absent():
    config = DosboxConfig.model_validate({})

    assert config.fullscreen is False


def test_cycles_is_kept_as_dosbox_wrote_it():
    """cycles is DOSBox's own free-form value ("max", "auto", "max 80%",
    "fixed 3000"...); DosboxConfig stores it verbatim and leaves
    interpreting it to dosbox_to_dosemu."""
    config = DosboxConfig.model_validate({"cpu": {"cycles": "fixed 3000"}})

    assert config.cycles == "fixed 3000"


def test_cycles_defaults_to_auto_when_absent():
    """DOSBox's own default for cycles."""
    config = DosboxConfig.model_validate({})

    assert config.cycles == "auto"


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


def test_memsize_defaults_to_16mb_when_absent():
    """DOSBox's own default for memsize."""
    config = DosboxConfig.model_validate({})

    assert config.memsize == 16


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


def test_dosbox_to_dosemu_carries_fullscreen_through_unchanged():
    target = dosbox_to_dosemu(DosboxConfig(fullscreen=True))

    assert target.X_fullscreen is True


def test_dosbox_to_dosemu_translates_speaker_and_serial_and_joystick():
    target = dosbox_to_dosemu(DosboxConfig(pcspeaker=True, serial1="dummy", joysticktype="none"))

    assert target.speaker == "emulated"
    assert target.com1 == ""
    assert target.joystick == ""

    target_alt = dosbox_to_dosemu(
        DosboxConfig(pcspeaker=False, serial1="directserial", joysticktype="auto")
    )

    assert target_alt.speaker == ""
    assert target_alt.com1 == ""  # Always returns empty for now
    assert target_alt.joystick == "/dev/input/js0"


def test_dosbox_to_dosemu_does_not_emit_video():
    """DOSBox's `output` is a host rendering-surface choice with no
    dosemu2 equivalent, so it is not translated and $_video is left out
    of the rendered conf entirely (dosemu2 defaults it to "vga")."""
    assert not hasattr(dosbox_to_dosemu(DosboxConfig(output="opengl")), "video")


@pytest.fixture
def default_dosemu_kwargs():
    return {
        "X_fullscreen": False,
        "cpuspeed": 0,
        "cpu_vm": "kvm",
        "dpmi": 131072,
        "sound": True,
        "sb_base": 0x220,
        "sb_irq": 7,
        "sb_dma": 1,
        "sb_hdma": 5,
        "gus": False,
        "mpu401_base": 0x330,
        "mpu401_irq": 9,
        "speaker": "emulated",
        "com1": "",
        "joystick": "/dev/input/js0",
    }


@pytest.mark.parametrize(("fullscreen", "rendered"), [(True, "on"), (False, "off")])
def test_model_dump_dosemurc_renders_fullscreen_as_on_off(
    fullscreen: bool, rendered: str, default_dosemu_kwargs
):
    kwargs = default_dosemu_kwargs.copy()
    kwargs["X_fullscreen"] = fullscreen
    target = DosemuConfig(**kwargs)

    output = target.model_dump_dosemurc()

    assert f"$_X_fullscreen = ({rendered})" in output.splitlines()


def test_model_dump_dosemurc_renders_dpmi_without_further_conversion(default_dosemu_kwargs):
    """dpmi is already in DOSEMU2's units by the time it reaches
    DosemuConfig; model_dump_dosemurc must not scale it again."""
    kwargs = default_dosemu_kwargs.copy()
    kwargs["dpmi"] = 262144
    target = DosemuConfig(**kwargs)

    output = target.model_dump_dosemurc()

    assert "$_dpmi = (262144)" in output.splitlines()


def test_model_dump_dosemurc_full_output(default_dosemu_kwargs):
    kwargs = default_dosemu_kwargs.copy()
    kwargs.update({"X_fullscreen": True, "cpuspeed": 3000, "dpmi": 131072})
    target = DosemuConfig(**kwargs)

    output = target.model_dump_dosemurc()

    assert "$_X_fullscreen = (on)" in output.splitlines()
    assert "$_cpuspeed = (3000)" in output.splitlines()
    assert "$_dpmi = (131072)" in output.splitlines()
