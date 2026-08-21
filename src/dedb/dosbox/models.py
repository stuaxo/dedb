"""Pydantic V2 models forming the anti-corruption layer between DOSBox and
DOSEMU2 configuration formats."""

from typing import ClassVar

from pydantic import AliasPath, BaseModel, Field, field_validator


class DosboxConfigToDosemu(BaseModel):
    """Reads a raw nested dosbox.conf dict and re-shapes it into DOSEMU2
    field names and units, ready to be dumped and fed into DosemuConfig.
    Field names match DOSEMU2's own config vars (X_fullscreen, cpuspeed,
    dpmi - see dosemu2's etc/dosemu.conf and src/include/emu.h) with the
    "$_" sigil dropped, since that's just dosemu.conf's
    variable-reference syntax, not part of the name. Unit/range
    conversion (DOSBox memsize -> DOSEMU2 dpmi) also happens here, so
    DosemuConfig only ever holds values already in DOSEMU2's own terms."""

    # DOSEMU2's documented default for $_dpmi (0x20000 Kb,
    # /etc/dosemu/dosemu.conf). Used as a floor under DOSBox's memsize,
    # not a ceiling - see coerce_dpmi.
    MIN_DPMI_MEMORY_MB: ClassVar[int] = 128

    fullscreen: bool = Field(
        default=False,
        validation_alias=AliasPath("sdl", "fullscreen"),
        serialization_alias="X_fullscreen",
    )
    cpu_speed: int = Field(
        default=0,
        validation_alias=AliasPath("cpu", "cycles"),
        serialization_alias="cpuspeed",
    )
    dpmi: int = Field(
        default=MIN_DPMI_MEMORY_MB * 1024,
        validation_alias=AliasPath("dosbox", "memsize"),
        serialization_alias="dpmi",
    )

    @field_validator("fullscreen", mode="before")
    @classmethod
    def coerce_fullscreen(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return value

    @field_validator("cpu_speed", mode="before")
    @classmethod
    def coerce_cpu_speed(cls, value: object) -> object:
        if isinstance(value, str):
            # dosbox "cycles" may be e.g. "max", "auto", "max 80%", "fixed 3000"
            first_token = value.strip().lower().split()[0] if value.strip() else ""
            if first_token in ("max", "auto"):
                return 0
            try:
                return int(first_token)
            except ValueError:
                return 0
        return value

    @field_validator("dpmi", mode="before")
    @classmethod
    def coerce_dpmi(cls, value: object) -> object:
        """Convert DOSBox memsize (MB) to DOSEMU2 $_dpmi (KB).

        DOSBOX has one pool of memory: `memsize`, while
        DOSEMU2 has seperate `XMS`, `EMS`, and `DPMI`.

        We can't know the right sizes at this point so choose to over-provision
        so that the DOS application doesn't run out of memory.
        """
        memsize_mb = cls.MIN_DPMI_MEMORY_MB
        if isinstance(value, str):
            try:
                memsize_mb = int(value.strip())
            except ValueError:
                memsize_mb = cls.MIN_DPMI_MEMORY_MB
        elif isinstance(value, int):
            memsize_mb = value
        return max(memsize_mb, cls.MIN_DPMI_MEMORY_MB) * 1024


class DosemuConfig(BaseModel):
    """
    Model of DOSEMU2 conf settings.

    IN general settings here should have names and units based off
    those in dosemu.conf.

    Names here don't have prefixes such as `$_` these are added
    when settings are written."""

    X_fullscreen: bool
    cpuspeed: int
    dpmi: int

    def model_dump_dosemurc(self) -> str:
        """Render as a DOSEMU2 config file: `$_var = (n)` for
        numeric/boolean values, `$_var = "s"` for strings
        (/etc/dosemu/dosemu.conf, dosemu2's src/base/init/lexer.l - bare
        on/off are keywords, plain decimal integers are valid).

        $_X_fullscreen: start DOSEMU2 in fullscreen.
        $_cpuspeed: CPU speed in MHz for TSC calibration; 0 = auto,
          matching the convention DosboxConfigToDosemu uses for DOSBox's
          auto/max cycles, though the two settings measure different
          things.
        $_dpmi: DPMI pool size in Kb - already converted/floored by
          DosboxConfigToDosemu.coerce_dpmi.
        """
        fullscreen = "on" if self.X_fullscreen else "off"
        lines = [
            f"$_X_fullscreen = ({fullscreen})",
            f"$_cpuspeed = ({self.cpuspeed})",
            f"$_dpmi = ({self.dpmi})",
        ]
        return "\n".join(lines) + "\n"
