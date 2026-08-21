"""Tests for dedb.dosbox.models.

DosboxConfigToDosemu reshapes a raw dosbox.conf dict into DOSEMU2 field
names and units; DosemuConfig renders those as a dosemu.conf.
"""

import pytest

from dedb.dosbox.models import DosboxConfigToDosemu, DosemuConfig


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
def test_fullscreen_string_coercion(raw: str, expected: bool):
    config = DosboxConfigToDosemu.model_validate({"sdl": {"fullscreen": raw}})

    assert config.fullscreen is expected


def test_fullscreen_defaults_to_false_when_absent():
    config = DosboxConfigToDosemu.model_validate({})

    assert config.fullscreen is False


@pytest.mark.parametrize(
    ("cycles", "expected_cpu_speed"),
    [
        ("max", 0),
        ("auto", 0),
        ("max 80%", 0),
        ("3000", 3000),
        ("  4000  ", 4000),
    ],
)
def test_cycles_string_coercion(cycles: str, expected_cpu_speed: int):
    config = DosboxConfigToDosemu.model_validate({"cpu": {"cycles": cycles}})

    assert config.cpu_speed == expected_cpu_speed


def test_fixed_cycles_are_not_read_as_a_speed():
    """DOSBox's "cycles=fixed N" and "cycles=N" set the same behaviour,
    but only the bare form is recognised here: the "fixed" token is not
    stripped, so int() fails and cpu_speed falls back to 0 (auto). This
    locks in the current behaviour; it is a candidate for a follow-up fix
    rather than something this test asserts is correct."""
    config = DosboxConfigToDosemu.model_validate({"cpu": {"cycles": "fixed 3000"}})

    assert config.cpu_speed == 0


def test_cpu_speed_defaults_to_zero_when_absent():
    config = DosboxConfigToDosemu.model_validate({})

    assert config.cpu_speed == 0


@pytest.mark.parametrize(
    ("memsize", "expected_dpmi_kb"),
    [
        ("16", 131072),  # below the floor: floored to 128Mb, then converted
        ("128", 131072),  # exactly the floor
        ("129", 132096),  # above the floor: converted, not floored
        ("256", 262144),
        ("not-a-number", 131072),  # unparsable: falls back to the floor
    ],
)
def test_memsize_is_floored_then_converted_to_kb(memsize: str, expected_dpmi_kb: int):
    config = DosboxConfigToDosemu.model_validate({"dosbox": {"memsize": memsize}})

    assert config.dpmi == expected_dpmi_kb


def test_dpmi_defaults_to_the_floor_when_memsize_is_absent():
    config = DosboxConfigToDosemu.model_validate({})

    assert config.dpmi == 131072


def test_dumps_with_dosemu_field_names():
    config = DosboxConfigToDosemu.model_validate(
        {"sdl": {"fullscreen": "true"}, "cpu": {"cycles": "3000"}, "dosbox": {"memsize": "256"}}
    )

    assert config.model_dump(by_alias=True) == {
        "X_fullscreen": True,
        "cpuspeed": 3000,
        "dpmi": 262144,
    }


def test_dosbox_output_feeds_dosemu_config_directly():
    """DosboxConfigToDosemu's by_alias dump must be a valid DosemuConfig
    input with no further transformation."""
    converted = DosboxConfigToDosemu.model_validate(
        {"sdl": {"fullscreen": "true"}, "cpu": {"cycles": "3000"}, "dosbox": {"memsize": "256"}}
    )

    target = DosemuConfig.model_validate(converted.model_dump(by_alias=True))

    assert target == DosemuConfig(X_fullscreen=True, cpuspeed=3000, dpmi=262144)


@pytest.mark.parametrize(
    ("fullscreen", "rendered"), [(True, "on"), (False, "off")]
)
def test_model_dump_dosemurc_renders_fullscreen_as_on_off(fullscreen: bool, rendered: str):
    target = DosemuConfig(X_fullscreen=fullscreen, cpuspeed=0, dpmi=131072)

    output = target.model_dump_dosemurc()

    assert f"$_X_fullscreen = ({rendered})" in output.splitlines()


def test_model_dump_dosemurc_renders_dpmi_without_further_conversion():
    """dpmi is already in DOSEMU2's units by the time it reaches
    DosemuConfig; model_dump_dosemurc must not scale it again."""
    target = DosemuConfig(X_fullscreen=False, cpuspeed=0, dpmi=262144)

    output = target.model_dump_dosemurc()

    assert "$_dpmi = (262144)" in output.splitlines()


def test_model_dump_dosemurc_full_output():
    target = DosemuConfig(X_fullscreen=True, cpuspeed=3000, dpmi=131072)

    assert target.model_dump_dosemurc() == (
        "$_X_fullscreen = (on)\n$_cpuspeed = (3000)\n$_dpmi = (131072)\n"
    )
