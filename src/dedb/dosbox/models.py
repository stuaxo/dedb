"""Pydantic V2 models forming the anti-corruption layer between DOSBox and
DOSEMU2 configuration formats.

DosboxConfig and DosemuConfig each reflect one side only: field names,
types and defaults match that side's own config file. dosbox_to_dosemu
is the one place a DOSBox setting becomes a DOSEMU2 setting - renaming
and unit conversion happen there, nowhere else."""

from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_validator

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
    joysticktype: str = Field(default="auto", validation_alias=AliasPath("joystick", "joysticktype"))

    # Render/Video fields
    aspect: bool = Field(default=False, validation_alias=AliasPath("render", "aspect"))
    scaler: str = Field(default="normal2x", validation_alias=AliasPath("render", "scaler"))
    output: str = Field(default="surface", validation_alias=AliasPath("sdl", "output"))

    @field_validator("fullscreen", "gus", "pcspeaker", "aspect", mode="before")
    @classmethod
    def coerce_bool(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return value

    @field_validator("memsize", "irq", "dma", "hdma", mode="before")
    @classmethod
    def coerce_int(cls, value: object, info) -> object:
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return cls.model_fields[info.field_name].default
        return value


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
    video: str = Field(serialization_alias="$_video")

    def model_dump_dosemurc(self) -> str:
        """Render as a DOSEMU2 config file: `$_var = (n)` for
        numeric/boolean values, `$_var = "s"` for strings
        (/etc/dosemu/dosemu.conf, dosemu2's src/base/init/lexer.l - bare
        on/off are keywords, plain decimal integers are valid).

        $_X_fullscreen: start DOSEMU2 in fullscreen.
        $_cpuspeed: CPU speed in MHz for TSC calibration; 0 = auto,
          matching the convention dosbox_to_dosemu uses for DOSBox's
          auto/max cycles, though the two settings measure different
          things.
        $_dpmi: DPMI pool size in Kb - already converted/floored by
          dosbox_to_dosemu.
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


def _cycles_to_cpuspeed(cycles: str) -> int:
    """DOSBox's cycles throttles emulated instructions per millisecond;
    DOSEMU2's cpuspeed calibrates a reported clock speed in MHz -
    different measurements that happen to share a "0 = auto" convention.
    cycles may be e.g. "max", "auto", "max 80%", "fixed 3000"; only a
    bare number carries a value across, anything else maps to 0."""
    first_token = cycles.strip().lower().split()[0] if cycles.strip() else ""
    if first_token in ("max", "auto"):
        return 0
    try:
        return int(first_token)
    except ValueError:
        return 0


def _memsize_to_dpmi_kb(memsize: int) -> int:
    """DOSBox shares one memsize figure (Mb) across XMS/EMS/DPMI; DOSEMU2
    sizes each pool separately (dosemu2 src/doc/README/config), and GOG
    confs frequently set memsize as low as 16Mb - copying it straight
    into $_dpmi would badly under-provision DPMI, so it's floored
    against DOSEMU2's own documented default before converting to Kb.
    Over-provisioning DPMI is safe; under-provisioning is fatal."""
    return max(memsize, MIN_DPMI_MEMORY_MB) * 1024


def _core_to_cpu_vm(core: str) -> str:
    """DOSBox throttles a fixed cycle count; DOSEmu2 runs near-native via KVM."""
    if core.strip().lower() == "normal":
        return "emulated"
    return "kvm"


def _sbtype_to_sound_enabled(sbtype: str) -> bool:
    """DOSBox emulates specific SoundBlaster chips; DOSEmu2 emulates fixed hardware and forwards to host audio."""
    return sbtype.strip().lower() != "none"


def _sbbase_to_hex(sbbase: str) -> int:
    """DOSBox implicitly uses hex for ports; DOSEmu2 requires explicit 0x prefix."""
    try:
        return int(sbbase.strip(), 16)
    except ValueError:
        return 0x220


def _mpu401_to_base(mpu401: str) -> int:
    """DOSBox uses various MIDI devices; DOSEmu2 exposes MPU-401 for host routing."""
    return 0 if mpu401.strip().lower() == "none" else 0x330


def _mpu401_to_irq(mpu401: str) -> int:
    """Default IRQ 9 for MPU-401 if enabled, 0 if none."""
    return 0 if mpu401.strip().lower() == "none" else 9


def _pcspeaker_to_speaker(pcspeaker: bool) -> str:
    """DOSBox synthesizes PC speaker; DOSEmu2 routes emulated speaker to host audio."""
    return "emulated" if pcspeaker else ""


def _serial_to_com(serial: str) -> str:
    """DOSBox provides dummy serial ports; DOSEmu2 requires explicit host device paths. Defaulting to disabled."""
    return ""


def _joystick_to_device(joysticktype: str) -> str:
    """DOSBox emulates specific joystick protocols; DOSEmu2 maps directly to host input devices."""
    return "" if joysticktype.strip().lower() == "none" else "/dev/input/js0"


def _output_to_video(output: str) -> str:
    """DOSBox selects SDL output surfaces (opengl, overlay, etc.); DOSEmu2 usually expects 'X' for windowed environments."""
    output_lower = output.strip().lower()
    return "X" if output_lower != "none" else ""


def dosbox_to_dosemu(dosbox: DosboxConfig) -> DosemuConfig:
    """Translate a DosboxConfig into a DosemuConfig. The only place
    DOSBox's field names and units become DOSEMU2's."""
    return DosemuConfig(
        X_fullscreen=dosbox.fullscreen,
        cpuspeed=_cycles_to_cpuspeed(dosbox.cycles),
        cpu_vm=_core_to_cpu_vm(dosbox.core),
        dpmi=_memsize_to_dpmi_kb(dosbox.memsize),
        sound=_sbtype_to_sound_enabled(dosbox.sbtype),
        sb_base=_sbbase_to_hex(dosbox.sbbase),
        sb_irq=dosbox.irq,
        sb_dma=dosbox.dma,
        sb_hdma=dosbox.hdma,
        gus=dosbox.gus,
        mpu401_base=_mpu401_to_base(dosbox.mpu401),
        mpu401_irq=_mpu401_to_irq(dosbox.mpu401),
        speaker=_pcspeaker_to_speaker(dosbox.pcspeaker),
        com1=_serial_to_com(dosbox.serial1),
        joystick=_joystick_to_device(dosbox.joysticktype),
        video=_output_to_video(dosbox.output),
    )
