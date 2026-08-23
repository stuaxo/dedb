from pydantic import AliasPath

def assert_validation_aliases_are_structural(model_cls):
    """Asserts that the validation_alias of every field in model_cls, if present,
    is an AliasPath that ends with the exact name of the field.
    This ensures aliases only locate values in a nested structure, without renaming."""
    for name, field in model_cls.model_fields.items():
        if field.validation_alias is not None:
            assert isinstance(field.validation_alias, AliasPath), f"Field {name} validation_alias must be an AliasPath"
            assert field.validation_alias.path[-1] == name, f"Field {name} validation_alias must end with its own name"


def assert_serialization_aliases_add_only_prefix(model_cls, prefix):
    """Asserts that the serialization_alias of every field in model_cls
    exactly matches the field's name prepended with the given prefix."""
    for name, field in model_cls.model_fields.items():
        expected_alias = f"{prefix}{name}"
        assert field.serialization_alias == expected_alias, (
            f"Field {name} serialization_alias {field.serialization_alias!r} "
            f"does not match expected {expected_alias!r}"
        )
