"""Pydantic V2 models for the DOSBox -> DOSEMU2 config translation.

Three models, a pipeline:

* ``DosboxConfig`` - the source. Fields, types and defaults are
  dosbox.conf's own; ``validation_alias`` locates each value in the
  parsed section dict. Answers questions about dosbox.conf.
* ``DosemuConfigFromDosbox`` - the translation. Its fields are
  ``DosemuConfig``'s, each ``validation_alias``'d to the ``DosboxConfig``
  field it comes from; a ``mode="before"`` validator does the unit/format
  conversion. ``Unsupported`` marks a dosbox setting read but deliberately
  not carried across.
* ``DosemuConfig`` - the destination. Fields, types and rendering are
  dosemu.conf's own; ``serialization_alias`` is the ``$_`` variable name.
  Answers questions about dosemu.conf.

``dosbox_to_dosemu`` runs the pipeline. ``dedb.convert.fieldmap`` reads
``DosemuConfigFromDosbox`` to generate the field map in ARCHITECTURE.md,
and ``test_fieldmap.py`` checks the three models line up.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_validator

from .mounts import MountPoint, resolve_mounts
from .validators import coerce_int, istruthy

# DOSEMU2's documented default for $_dpmi (0x20000 Kb,
# /etc/dosemu/dosemu.conf). Used as a floor under DOSBox's memsize, not
# a ceiling - see _memsize_to_dpmi_kb.
MIN_DPMI_MEMORY_MB = 128


class DosboxConfig(BaseModel):
    """Represents fields in dosbox.conf

    Field names and types should match those in dosbox.conf

    The data structure is flaat, validation_alias is used to
    pull data from the sections of the dosbox.conf.
    """

    model_config = ConfigDict(populate_by_name=True)

    fullscreen: bool = Field(default=False, validation_alias=AliasPath("sdl", "fullscreen"))
    cycles: str = Field(default="auto", validation_alias=AliasPath("cpu", "cycles"))
    core: str = Field(default="auto", validation_alias=AliasPath("cpu", "core"))
    memsize: int = Field(default=16, validation_alias=AliasPath("dosbox", "memsize"))

    # Sound fields
    sbtype: str = Field(default="sb16", validation_alias=AliasPath("sblaster", "sbtype"))
    sbbase: str = Field(default="220", validation_alias=AliasPath("sblaster", "sbbase"))
    irq: int = Field(default=7, validation_alias=AliasPath("sblaster", "irq"))
    dma: int = Field(default=1, validation_alias=AliasPath("sblaster", "dma"))
    hdma: int = Field(default=5, validation_alias=AliasPath("sblaster", "hdma"))
    gus: bool = Field(default=False, validation_alias=AliasPath("gus", "gus"))
    mpu401: str = Field(default="intelligent", validation_alias=AliasPath("midi", "mpu401"))
    pcspeaker: bool = Field(default=True, validation_alias=AliasPath("speaker", "pcspeaker"))

    # Serial fields
    serial1: str = Field(default="dummy", validation_alias=AliasPath("serial", "serial1"))

    # Joystick fields
    joysticktype: str = Field(
        default="auto", validation_alias=AliasPath("joystick", "joysticktype")
    )

    # Render/Video fields. Parsed so a `config -set` targeting them isn't
    # flagged as unknown, but deliberately not translated (see the
    # Unsupported fields on DosemuConfigFromDosbox): aspect-ratio
    # correction, the scaler algorithm and the output backend are all
    # host-side rendering choices with no DOSEMU2 equivalent.
    aspect: bool = Field(default=False, validation_alias=AliasPath("render", "aspect"))
    scaler: str = Field(default="normal2x", validation_alias=AliasPath("render", "scaler"))
    output: str = Field(default="surface", validation_alias=AliasPath("sdl", "output"))

    # [autoexec]
    # Each entry in autoexec is a line in the autoexec.bat
    autoexec: list[str] = Field(default_factory=list)

    _coerce_bool = field_validator("fullscreen", "gus", "pcspeaker", "aspect", mode="before")(
        istruthy
    )
    _coerce_int = field_validator("memsize", "irq", "dma", "hdma", mode="before")(coerce_int)

    @classmethod
    def from_sections(cls, sections: dict, autoexec: Sequence[str] = ()) -> "DosboxConfig":
        """Build from the parser's ``(section dict, autoexec lines)`` output
        (``dedb.convert.parser`` / ``dedb.convert.cmdline``)."""
        return cls.model_validate({**sections, "autoexec": list(autoexec)})

    def get_mounts(self, working_dir: Path) -> list[MountPoint]:
        """Every ``MOUNT`` command in the autoexec, each target resolved
        against ``working_dir`` into a host path (see
        ``dedb.convert.mounts``). IMGMOUNT and unmounts are skipped."""
        return resolve_mounts(self.autoexec, working_dir)

    @classmethod
    def config_keys_by_section(cls) -> dict[str, dict[str, str]]:
        """``{section: {key: field_name}}`` for every modelled dosbox.conf
        item, read from each field's ``validation_alias`` (``alias.path[0]``
        is the section, ``alias.path[-1]`` the key). Lets a caller building
        a config from somewhere other than a .conf file (e.g. a command
        line's ``config -set section key=value``) check a section/key pair
        is one this model actually reads."""
        by_section: dict[str, dict[str, str]] = {}
        for name, field in cls.model_fields.items():
            alias = field.validation_alias
            if not isinstance(alias, AliasPath):
                continue

            by_section.setdefault(alias.path[0], {})[alias.path[-1]] = name
        return by_section


class DosemuConfig(BaseModel):
    """Model of DOSEMU2 conf settings.

    Settings here should have names and units consistent with
    dosemu.conf but without the `$_` prefix.

    Fields use serialization_alias to the dosemu.conf native
    name with it's `$_` prefix.

    See `model_dump_dosemurc` to see where `dosemu.conf`
    is written."""

    X_fullscreen: bool = Field(
        serialization_alias="$_X_fullscreen", description="Enable fullscreen mode."
    )

    cpuspeed: int = Field(
        serialization_alias="$_cpuspeed",
        description="CPU speed in MHz for TSC calibration; 0 = auto.",
    )

    cpu_vm: str = Field(serialization_alias="$_cpu_vm")
    dpmi: int = Field(serialization_alias="$_dpmi", description="DPMI pool size in Kb.")

    # Sound fields
    sound: bool = Field(serialization_alias="$_sound")
    sb_base: int = Field(serialization_alias="$_sb_base")
    sb_irq: int = Field(serialization_alias="$_sb_irq")
    sb_dma: int = Field(serialization_alias="$_sb_dma")
    sb_hdma: int = Field(serialization_alias="$_sb_hdma")
    gus: bool = Field(serialization_alias="$_gus")
    mpu401_base: int = Field(serialization_alias="$_mpu401_base")
    mpu401_irq: int = Field(serialization_alias="$_mpu401_irq")
    speaker: str = Field(serialization_alias="$_speaker")

    # Serial fields
    com1: str = Field(serialization_alias="$_com1")

    # Joystick fields
    joystick: str = Field(serialization_alias="$_joystick")

    # Render/Video fields:
    #
    # No $_video field: dosemu2's $_video is the emulated video *adapter*
    # style (one of vga/ega/mda/mga/cga/none), not a display backend.

    def model_dump_dosemurc(self) -> str:
        """Render as a DOSEMU2 `dosemu.conf`:

        # numeric / boolean values:
        `$_var = (n)`

        # strings values:
        `$_var = "s"`

        $_X_fullscreen: start DOSEMU2 in fullscreen.
        $_cpuspeed: CPU speed in MHz for TSC calibration; 0 = auto.
        $_dpmi: DPMI pool size in Kb - already converted/floored upstream.
        """
        lines = []
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if isinstance(value, bool):
                rendered = f"({'on' if value else 'off'})"
            elif name in ("sb_base", "mpu401_base") and isinstance(value, int):
                rendered = f"({hex(value)})"
            elif isinstance(value, str):
                rendered = f'"{value}"'
            else:
                rendered = f"({value})"
            lines.append(f"{field.serialization_alias} = {rendered}")
        return "\n".join(lines) + "\n"


Unsupported = Annotated[Any, Field(default=None, exclude=True)]
"""DOSBox setting that is not currently output as a DOSEMU2 setting"""


class DosemuConfigFromDosbox(BaseModel):
    """Pydantic model to translate ``DosboxConfig`` to ``DosemuConfig``.

    Fields are named to match the destination model (``DosemuConfig``),
    and validation_alias is set to match the source model (``DosboxConfig``).

    validators are used to convert units and formats from DOSBox to DOSEMU2.
    """

    model_config = ConfigDict(populate_by_name=True)

    X_fullscreen: bool = Field(validation_alias="fullscreen")
    cpuspeed: int = Field(
        validation_alias="cycles",
        description="bare number kept as MHz; max / auto / anything else -> 0 (auto)",
    )
    cpu_vm: str = Field(
        validation_alias="core",
        description="'normal' -> emulated, otherwise kvm (DOSEMU2 runs near-native)",
    )
    dpmi: int = Field(
        validation_alias="memsize",
        description="floored to DOSEMU2's 128 MB DPMI default, then MB -> KB",
    )
    sound: bool = Field(
        validation_alias="sbtype",
        description="any SoundBlaster type -> sound on; 'none' -> off",
    )
    sb_base: int = Field(
        validation_alias="sbbase", description="decimal-looking port string parsed as hex"
    )
    sb_irq: int = Field(validation_alias="irq")
    sb_dma: int = Field(validation_alias="dma")
    sb_hdma: int = Field(validation_alias="hdma")
    gus: bool = Field(validation_alias="gus")
    mpu401_base: int = Field(validation_alias="mpu401", description="'none' -> 0, otherwise 0x330")
    mpu401_irq: int = Field(validation_alias="mpu401", description="'none' -> 0, otherwise 9")
    speaker: str = Field(
        validation_alias="pcspeaker", description="on -> 'emulated', off -> '' (disabled)"
    )
    com1: str = Field(
        validation_alias="serial1", description="always '' - DOSEMU2 needs a real host device path"
    )
    joystick: str = Field(
        validation_alias="joysticktype", description="'none' -> '', otherwise /dev/input/js0"
    )

    aspect: Unsupported = Field(validation_alias="aspect")
    scaler: Unsupported = Field(validation_alias="scaler")
    output: Unsupported = Field(validation_alias="output")

    @field_validator("cpuspeed", mode="before")
    @classmethod
    def _cycles_to_cpuspeed(cls, cycles: str) -> int:
        """DOSBox's cycles throttles emulated instructions per millisecond;
        DOSEMU2's cpuspeed calibrates a reported clock speed in MHz -
        different measurements that happen to share a "0 = auto"
        convention. cycles may be e.g. "max", "auto", "max 80%",
        "fixed 3000"; only a bare number carries a value across, anything
        else maps to 0."""
        first_token = cycles.strip().lower().split()[0] if cycles.strip() else ""
        if first_token in ("max", "auto"):
            return 0
        try:
            return int(first_token)
        except ValueError:
            return 0

    @field_validator("dpmi", mode="before")
    @classmethod
    def _memsize_to_dpmi_kb(cls, memsize: int) -> int:
        """DOSBox shares one memsize figure (Mb) across XMS/EMS/DPMI;
        DOSEMU2 sizes each pool separately (dosemu2
        src/doc/README/config), and GOG confs frequently set memsize as
        low as 16Mb - copying it straight into $_dpmi would badly
        under-provision DPMI, so it's floored against DOSEMU2's own
        documented default before converting to Kb. Over-provisioning
        DPMI is safe; under-provisioning is fatal."""
        return max(memsize, MIN_DPMI_MEMORY_MB) * 1024

    @field_validator("cpu_vm", mode="before")
    @classmethod
    def _core_to_cpu_vm(cls, core: str) -> str:
        """DOSBox throttles a fixed cycle count; DOSEMU2 runs near-native via KVM."""
        return "emulated" if core.strip().lower() == "normal" else "kvm"

    @field_validator("sound", mode="before")
    @classmethod
    def _sbtype_to_sound_enabled(cls, sbtype: str) -> bool:
        """DOSBox emulates specific SoundBlaster chips; DOSEMU2 emulates
        fixed hardware and forwards to host audio."""
        return sbtype.strip().lower() != "none"

    @field_validator("sb_base", mode="before")
    @classmethod
    def _sbbase_to_hex(cls, sbbase: str) -> int:
        """DOSBox implicitly uses hex for ports; DOSEMU2 requires an explicit 0x prefix."""
        try:
            return int(sbbase.strip(), 16)
        except ValueError:
            return 0x220

    @field_validator("mpu401_base", mode="before")
    @classmethod
    def _mpu401_to_base(cls, mpu401: str) -> int:
        """DOSBox uses various MIDI devices; DOSEMU2 exposes MPU-401 for host routing."""
        return 0 if mpu401.strip().lower() == "none" else 0x330

    @field_validator("mpu401_irq", mode="before")
    @classmethod
    def _mpu401_to_irq(cls, mpu401: str) -> int:
        """IRQ 9 for MPU-401 when enabled, 0 when none."""
        return 0 if mpu401.strip().lower() == "none" else 9

    @field_validator("speaker", mode="before")
    @classmethod
    def _pcspeaker_to_speaker(cls, pcspeaker: bool) -> str:
        """DOSBox synthesizes the PC speaker; DOSEMU2 routes the emulated speaker to host audio."""
        return "emulated" if pcspeaker else ""

    @field_validator("com1", mode="before")
    @classmethod
    def _serial_to_com(cls, serial1: str) -> str:
        """DOSBox provides dummy serial ports; DOSEMU2 needs a real host
        device path, so serial is left disabled."""
        return ""

    @field_validator("joystick", mode="before")
    @classmethod
    def _joysticktype_to_device(cls, joysticktype: str) -> str:
        """DOSBox emulates specific joystick protocols; DOSEMU2 maps directly to host input devices."""
        return "" if joysticktype.strip().lower() == "none" else "/dev/input/js0"

    @classmethod
    def translated_fields(cls) -> list[str]:
        """The field names that map to a DosemuConfig field (i.e. not the
        Unsupported ones)."""
        return [name for name, field in cls.model_fields.items() if not field.exclude]


def dosbox_to_dosemu(dosbox: DosboxConfig) -> DosemuConfig:
    """Translate a DosboxConfig into a DosemuConfig through the
    DosemuConfigFromDosbox layer - field aliases rename, validators
    convert, Unsupported settings drop out."""
    translated = DosemuConfigFromDosbox.model_validate(dosbox.model_dump())
    return DosemuConfig(**translated.model_dump())
