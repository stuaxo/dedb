def istruthy(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return value


def coerce_int(cls, value: object, info) -> object:
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return cls.model_fields[info.field_name].default
    return value
