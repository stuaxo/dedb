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
    """Flat model of the subset of dosbox.conf this app reads. Field
    names, types and defaults match DOSBox's own dosbox.conf - no
    DOSEMU2 concepts here.

    validation_alias locates each value in dosbox.conf's nested section
    structure; populate_by_name still allows building an instance
    directly from its own field names (e.g. in tests), since the leaf of
    each alias already matches the field name - the alias is structural,
    not a rename."""

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

    # The [autoexec] block: an ordered list of DOS command lines, kept
    # verbatim. Unlike every other field this isn't a section/key lookup,
    # so it carries no AliasPath - the parser passes it in by name.
    autoexec: list[str] = Field(default_factory=list)

    coerce_bool = field_validator("fullscreen", "gus", "pcspeaker", "aspect", mode="before")(
        istruthy
    )
    coerce_int = field_validator("memsize", "irq", "dma", "hdma", mode="before")(coerce_int)

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
                continue  # `autoexec` - a verbatim list, not a section/key value
            by_section.setdefault(alias.path[0], {})[alias.path[-1]] = name
        return by_section


class DosemuConfig(BaseModel):
    """Model of DOSEMU2 conf settings.

    In general, settings here should have names and units based off
    those in dosemu.conf.

    Field names don't carry the `$_` prefix themselves; each field's
    serialization_alias is dosemu.conf's actual variable name (with the
    prefix) and is the only place that prefix is added - see
    model_dump_dosemurc."""

    X_fullscreen: bool = Field(serialization_alias="$_X_fullscreen")
    cpuspeed: int = Field(serialization_alias="$_cpuspeed")
    cpu_vm: str = Field(serialization_alias="$_cpu_vm")
    dpmi: int = Field(serialization_alias="$_dpmi")

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

    # Render/Video fields
    #
    # No $_video field: dosemu2's $_video is the emulated video *adapter*
    # style (one of vga/ega/mda/mga/cga/none), not a display backend.
    # DOSBox's `output` (surface/opengl/texture/...) selects a host
    # rendering surface and has no dosemu2 equivalent - dosemu2 chooses
    # its own backend (SDL) and defaults $_video to "vga", which is what
    # DOS games want anyway. Emitting `$_video = "X"` (the old DOSEMU1
    # spelling for "use X") actually breaks dosemu2: its built-in
    # global.conf expands $_video into `video { X }`, a parse error that
    # aborts startup.

    def model_dump_dosemurc(self) -> str:
        """Render as a DOSEMU2 config file: `$_var = (n)` for
        numeric/boolean values, `$_var = "s"` for strings
        (/etc/dosemu/dosemu.conf, dosemu2's src/base/init/lexer.l - bare
        on/off are keywords, plain decimal integers are valid).

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


# A DOSBox setting dedb reads (so `config -set` targeting it isn't flagged
# as unknown) but has no DOSEMU2 equivalent for. The value is dropped:
# excluded from model_dump, so it never reaches DosemuConfig.
Unsupported = Annotated[Any, Field(default=None, exclude=True)]


class DosemuConfigFromDosbox(BaseModel):
    """The translation layer: ``DosemuConfig``'s fields, each read from
    the ``DosboxConfig`` field its ``validation_alias`` names and put
    through a ``mode="before"`` validator that does the unit/format
    conversion. ``dosbox_to_dosemu`` feeds it ``DosboxConfig.model_dump()``
    and builds a ``DosemuConfig`` from the result. Field order matches the
    field map in ARCHITECTURE.md; each field's ``description`` is the
    one-line gloss the map prints, the validator's docstring the rationale."""

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
