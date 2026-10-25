"""The vocabulary stays in step across the enums and the ``code`` template (slice 402, D8).

Three copies of the review vocabulary exist: ``AuditCategory`` (with the audit skill,
guarded by ``test_audit_skill_sync.py``), ``ReviewCategory``, and the category block in
``code.yaml``'s prompt. A prompt and a Python enum cannot import from each other, so this
test is what makes drift in any one of them fail CI.
"""

from __future__ import annotations

from squadron.core.finding_categories import AuditCategory, ReviewCategory
from squadron.data import data_dir
from squadron.review.templates import ReviewTemplate, load_template
from tests.metrology.sync_helpers import BACKTICKED

#: The line that opens the vocabulary list in the prompt; the list runs to the next blank line.
VOCABULARY_HEADING = "Category vocabulary:"


def builtin(name: str) -> ReviewTemplate:
    return load_template(data_dir() / "templates" / f"{name}.yaml")


def vocabulary_block(prompt: str) -> str:
    """The lines from the vocabulary heading to the next blank line."""
    lines = prompt.splitlines()
    assert VOCABULARY_HEADING in (line.strip() for line in lines), (
        f"code.yaml's prompt has no '{VOCABULARY_HEADING}' line"
    )
    start = next(i for i, line in enumerate(lines) if line.strip() == VOCABULARY_HEADING)
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    return "\n".join(lines[start:end])


def test_review_categories_are_the_audit_categories_plus_correctness() -> None:
    assert {m.value for m in ReviewCategory} == {m.value for m in AuditCategory} | {"correctness"}
    assert "correctness" not in {m.value for m in AuditCategory}


def test_code_template_vocabulary_block_matches_the_enum_in_both_directions() -> None:
    block = vocabulary_block(builtin("code").system_prompt)

    found = set(BACKTICKED.findall(block))
    expected = {m.value for m in ReviewCategory}

    assert not expected - found, (
        f"ReviewCategory values missing from code.yaml: {sorted(expected - found)}"
    )
    assert not found - expected, (
        f"code.yaml lists values not in ReviewCategory: {sorted(found - expected)}"
    )


def test_only_the_code_template_normalizes_categories() -> None:
    assert builtin("code").normalize_categories is True
    for name in ("arch", "slice", "tasks"):
        assert builtin(name).normalize_categories is False, name
