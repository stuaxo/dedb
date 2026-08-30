"""Structural checks for the naming rule the DOSBox/DOSEMU2 model
pipeline is built on (see dedb.dosbox.models): a "left" model's fields
mirror its source format, a "right" model's fields mirror its target
format, and any alias on either one only locates or decorates a value -
it never renames it. Renaming happens in exactly one place, the
translation function between the two models (e.g. dosbox_to_dosemu).

Use assert_validation_aliases_are_structural for a left model (values
looked up by AliasPath in a nested raw dict) and
assert_serialization_aliases_add_only_prefix for a right model (values
written out under a fixed-prefix variable name).
"""

from pydantic import AliasPath, BaseModel


def assert_validation_aliases_are_structural(model_cls: type[BaseModel]) -> None:
    """Every field's validation_alias must be an AliasPath whose last
    segment is the field's own name. That means the alias only locates a
    value inside the source format's nested structure - it does not
    rename it."""
    for name, field in model_cls.model_fields.items():
        alias = field.validation_alias
        assert isinstance(alias, AliasPath), (
            f"{model_cls.__name__}.{name} has no AliasPath validation_alias "
            "to check"
        )
        assert alias.path[-1] == name, (
            f"{model_cls.__name__}.{name}'s validation_alias locates "
            f"{alias.path!r}, whose last segment isn't {name!r} - the "
            "alias is renaming the value, not just locating it"
        )


def assert_serialization_aliases_add_only_prefix(model_cls: type[BaseModel], prefix: str) -> None:
    """Every field's serialization_alias must be exactly prefix + the
    field's own name. That means the alias only adds the target format's
    variable-reference syntax - it does not rename the value."""
    for name, field in model_cls.model_fields.items():
        expected = f"{prefix}{name}"
        assert field.serialization_alias == expected, (
            f"{model_cls.__name__}.{name}'s serialization_alias is "
            f"{field.serialization_alias!r}, not {expected!r} - the alias "
            "is renaming the value, not just adding the prefix"
        )
