"""Tests for dedb.dosbox.models.

DosboxConfig mirrors dosbox.conf's own vocabulary; DosemuConfig mirrors
dosemu.conf's. dosbox_to_dosemu is the only place field names and units
cross from one side to the other.
"""

import pytest
from model_naming import (
    assert_serialization_aliases_add_only_prefix,
    assert_validation_aliases_are_structural,
)

from dedb.dosbox.models import DosboxConfig, DosemuConfig, dosbox_to_dosemu

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
    config = DosboxConfig.model_validate({"sdl": {"fullscreen": raw}})

    assert config.fullscreen is expected


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


@pytest.mark.parametrize(("fullscreen", "rendered"), [(True, "on"), (False, "off")])
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
