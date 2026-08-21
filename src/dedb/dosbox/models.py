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
    memsize: int = Field(default=16, validation_alias=AliasPath("dosbox", "memsize"))

    @field_validator("fullscreen", mode="before")
    @classmethod
    def coerce_fullscreen(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return value

    @field_validator("memsize", mode="before")
    @classmethod
    def coerce_memsize(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return 16
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
    dpmi: int = Field(serialization_alias="$_dpmi")

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
            rendered = ("on" if value else "off") if isinstance(value, bool) else value
            lines.append(f"{field.serialization_alias} = ({rendered})")
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


def dosbox_to_dosemu(dosbox: DosboxConfig) -> DosemuConfig:
    """Translate a DosboxConfig into a DosemuConfig. The only place
    DOSBox's field names and units become DOSEMU2's."""
    return DosemuConfig(
        X_fullscreen=dosbox.fullscreen,
        cpuspeed=_cycles_to_cpuspeed(dosbox.cycles),
        dpmi=_memsize_to_dpmi_kb(dosbox.memsize),
    )
