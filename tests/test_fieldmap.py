"""Tests for dedb.dosbox.fieldmap and the model invariants it relies on.

These lock the DOSBox<->DOSEMU2 field map to the code: every DosemuConfig
field must be produced by a translation, every DosboxConfig field must be
either translated or explicitly listed as not, and ARCHITECTURE.md's
generated table must be current.
"""

from dedb.dosbox import fieldmap
from dedb.dosbox.models import (
    TRANSLATIONS,
    UNTRANSLATED_DOSBOX_FIELDS,
    DosboxConfig,
    DosemuConfig,
)


def test_every_dosemu_field_is_filled_by_exactly_one_translation():
    targets = [t.target for t in TRANSLATIONS]
    assert sorted(targets) == sorted(DosemuConfig.model_fields)
    assert len(targets) == len(set(targets))  # no field written twice


def test_every_dosbox_field_is_translated_or_explicitly_not():
    accounted = {t.source for t in TRANSLATIONS} | set(UNTRANSLATED_DOSBOX_FIELDS)
    assert accounted == set(DosboxConfig.model_fields)


def test_translation_sources_and_untranslated_do_not_overlap():
    assert not {t.source for t in TRANSLATIONS} & set(UNTRANSLATED_DOSBOX_FIELDS)


def test_a_translation_with_no_converter_has_no_note():
    # "copied unchanged" straight-through translations carry no gloss;
    # anything with a note must also have a converter behind it.
    for t in TRANSLATIONS:
        if t.note:
            assert t.via is not None, f"{t.source}->{t.target} has a note but no converter"


def test_architecture_md_table_is_current():
    assert fieldmap.main(["--check"]) == 0, (
        "ARCHITECTURE.md field map is stale - run `python -m dedb.dosbox.fieldmap --write`"
    )


def test_render_markdown_lists_every_field():
    table = fieldmap.render_markdown()
    for name, field in DosemuConfig.model_fields.items():
        assert field.serialization_alias in table, name
    for name in UNTRANSLATED_DOSBOX_FIELDS:
        alias = DosboxConfig.model_fields[name].validation_alias
        assert f"[{alias.path[0]}] {alias.path[-1]}" in table
