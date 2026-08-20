"""Pydantic V2 models forming the anti-corruption layer between DOSBox and
DOSEMU2 configuration formats."""

from pydantic import AliasPath, BaseModel, Field, field_validator


class DosboxConfigToDosemu(BaseModel):
    """Reads a raw nested dosbox.conf dict and re-shapes it into DOSEMU2
    field names, ready to be dumped and fed into DosemuConfig."""

    fullscreen: bool = Field(
        default=False,
        validation_alias=AliasPath("sdl", "fullscreen"),
        serialization_alias="video_fullscreen",
    )
    cpu_speed: int = Field(
        default=0,
        validation_alias=AliasPath("cpu", "cycles"),
        serialization_alias="cpu_speed",
    )
    memory: int = Field(
        default=32,
        validation_alias=AliasPath("dosbox", "memsize"),
        serialization_alias="dpmi_memory",
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

    @field_validator("memory", mode="before")
    @classmethod
    def coerce_memory(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return 32
        return value


class DosemuConfig(BaseModel):
    """Flat model representing the final DOSEMU2 hardware settings."""

    video_fullscreen: bool
    cpu_speed: int
    dpmi_memory: int
