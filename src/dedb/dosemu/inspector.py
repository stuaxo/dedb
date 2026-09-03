"""Render the converted DOSEMU2 output for `dedb dosemuconf`.

Thin: the `dosemu.conf` text is already rendered
(`DosemuConfig.model_dump_dosemurc`) and `userhook.bat` is a list of
lines. This just arranges the blocks - one `[label]` section per launch
profile when there is more than one.
"""

from collections.abc import Sequence

Entry = tuple[str, str, Sequence[str]]  # (label, dosemu.conf text, userhook.bat lines)


def render(
    entries: Sequence[Entry], *, conf: bool, userhook: bool, issues_block: str | None
) -> str:
    """`entries` is one `(label, conf_text, userhook_lines)` per profile.

    With none of `conf` / `userhook` / `issues_block` selected, both the
    conf and the userhook are shown. Otherwise exactly what was asked,
    issues first. A `[label]` header precedes each entry when there is
    more than one.
    """
    asked = conf or userhook or issues_block is not None
    show_conf = conf or not asked
    show_userhook = userhook or not asked
    multi = len(entries) > 1

    blocks: list[str] = []
    if issues_block is not None:
        blocks.append(issues_block)

    for label, conf_text, userhook_lines in entries:
        parts = []
        if show_conf:
            parts.append(conf_text.rstrip("\n"))
        if show_userhook:
            parts.append("\n".join(userhook_lines))
        body = "\n\n".join(part for part in parts if part)
        blocks.append(f"[{label}]\n{body}" if multi else body)

    return "\n\n".join(block for block in blocks if block)
