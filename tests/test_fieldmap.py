"""Integrity of the three-model translation pipeline, and the generated
ARCHITECTURE.md field map.

DosboxConfig (src) -> DosemuConfigFromDosbox (translation) -> DosemuConfig
(dest). These tests check the ends line up: every translation field reads
a real dosbox field, and its translated fields are exactly the dosemu
fields.
"""

from dedb.convert import fieldmap
from dedb.convert.models import DosboxConfig, DosemuConfig, DosemuConfigFromDosbox

# `autoexec` is the [autoexec] command list, handled by the shim pipeline
# (dedb.convert.autoexec), not a scalar setting the translation touches.
_DOSBOX_SETTINGS = {name for name in DosboxConfig.model_fields if name != "autoexec"}


def _translation_aliases() -> dict[str, str]:
    """{translation field name: the DosboxConfig field it reads}."""
    return {
        name: field.validation_alias for name, field in DosemuConfigFromDosbox.model_fields.items()
    }


def test_translation_reads_only_real_dosbox_fields():
    """src -> translation: every DosemuConfigFromDosbox field's
    validation_alias names a field that exists on DosboxConfig."""
    unknown = set(_translation_aliases().values()) - set(DosboxConfig.model_fields)
    assert not unknown, f"translation reads dosbox fields that don't exist: {unknown}"


def test_translation_covers_every_dosbox_setting():
    """No dosbox setting is silently ignored - each is either translated
    or explicitly marked Unsupported."""
    assert set(_translation_aliases().values()) == _DOSBOX_SETTINGS


def test_translated_fields_are_exactly_the_dosemu_fields():
    """translation -> dest: the non-Unsupported translation fields match
    DosemuConfig's fields one-to-one."""
    assert sorted(DosemuConfigFromDosbox.translated_fields()) == sorted(DosemuConfig.model_fields)


def test_unsupported_fields_produce_nothing():
    """An Unsupported field is read from dosbox but excluded from the
    dump, so it never reaches DosemuConfig."""
    excluded = {n for n, f in DosemuConfigFromDosbox.model_fields.items() if f.exclude}
    assert excluded == {"aspect", "scaler", "output"}
    assert not excluded & set(DosemuConfig.model_fields)


def test_architecture_md_table_is_current():
    assert fieldmap.main(["--check"]) == 0, (
        "ARCHITECTURE.md field map is stale - run `python -m dedb.convert.fieldmap --write`"
    )


def test_render_markdown_lists_every_field():
    table = fieldmap.render_markdown()
    for field in DosemuConfig.model_fields.values():
        assert field.serialization_alias in table
    for name in ("aspect", "scaler", "output"):
        alias = DosboxConfig.model_fields[name].validation_alias
        assert f"[{alias.path[0]}] {alias.path[-1]}" in table
