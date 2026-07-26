"""The fork-sync guard: squadron's vendored skill and ``AuditCategory`` agree.

The ``tech-debt-audit`` skill has two homes that must not drift: the
canonical fork (``github:ecorkran/tech-debt-audit``) and the copy vendored
into ``commands/analysis/``. The category vocabulary is duplicated across a
process boundary — a markdown prompt and a Python enum cannot import from
each other — so this module is the mechanical enforcement that keeps them
identical.

Drift here is a *silent* failure in production, which is why it is caught
loudly in CI: ``audit_prompt_hash`` correctly refuses to pool audits taken
under differing prompts, so a fork edit that skips the squadron sync
produces audits that simply never compare, with no error to notice.

The skill is located via ``_resolve_bundled`` — the same lookup the harness
uses — rather than a hard-coded relative path, so this exercises the real
resolution.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadron.metrology.audit import INDEPENDENT_RUN_MARKER
from squadron.metrology.audit_models import AuditCategory
from squadron.skills.resolver import _resolve_bundled  # pyright: ignore[reportPrivateUsage]

#: The vocabulary is enumerated in the skill's category table as backticked
#: kebab-case values. Matching backticked tokens (rather than a fixed table
#: layout) keeps this lenient about formatting: reflowing the table, or
#: switching it to a bullet list, must not break the guard.
_BACKTICKED = re.compile(r"`([a-z][a-z-]*[a-z])`")


@pytest.fixture
def skill_text() -> str:
    """The vendored skill file, resolved the way the harness resolves it."""
    path: Path = _resolve_bundled("analysis") / "tech-debt-audit.md"
    assert path.is_file(), f"vendored audit skill not found at {path}"
    return path.read_text(encoding="utf-8")


def test_category_vocabulary_matches_enum(skill_text: str) -> None:
    """Every ``AuditCategory`` value appears in the skill, and none besides.

    This is the CI guard against fork/squadron drift. It must fail loudly if
    either side changes alone — deleting a value from the skill file, or
    adding one to the enum without syncing the fork, both break it.
    """
    expected = {member.value for member in AuditCategory}
    found = set(_BACKTICKED.findall(skill_text))

    missing = expected - found
    assert not missing, (
        f"AuditCategory values absent from the vendored skill file: {sorted(missing)}. "
        "The fork and squadron have drifted — re-vendor from the canonical fork."
    )

    # The skill backticks other kebab-case prose tokens, so the reverse
    # direction is scoped to the category table itself.
    table = skill_text.split("### Category vocabulary", 1)
    assert len(table) == 2, "skill file has no '### Category vocabulary' section"
    table_values = set(_BACKTICKED.findall(table[1].split("## Phase 3", 1)[0]))
    extra = table_values - expected
    assert not extra, (
        f"skill file enumerates categories absent from AuditCategory: {sorted(extra)}. "
        "An invented category is data the baseline cannot compare across audits."
    )


def test_findings_delimiters_present_exactly_once(skill_text: str) -> None:
    """Both block delimiters appear exactly once — the parser locates on them."""
    assert skill_text.count("squadron:findings:begin") == 1
    assert skill_text.count("squadron:findings:end") == 1


def test_independent_run_marker_matches_harness_constant(skill_text: str) -> None:
    """The marker the harness sends is the marker the skill documents.

    Defined once as a module constant in ``audit.py`` and asserted here, so
    a reworded marker cannot silently stop suppressing repeat-run mode.
    """
    assert INDEPENDENT_RUN_MARKER in skill_text


def test_repeat_run_clause_is_conditional(skill_text: str) -> None:
    """Repeat-run mode is scoped by an explicit independent-run exception.

    Asserting the marker exists *somewhere* is not enough: an unconditional
    repeat-run clause would still make run 2 of a variance series read run
    1's output, correlating the runs and biasing the measured floor toward
    zero — the worst direction, since it makes every later delta look
    significant. So this asserts the rewording actually landed.
    """
    section = skill_text.split("## Repeat-run mode", 1)
    assert len(section) == 2, "skill file has no '## Repeat-run mode' section"
    clause = section[1].split("##", 1)[0]

    assert "independent run" in clause.lower(), (
        "the repeat-run clause does not reference the independent-run exception; "
        "an unconditional clause correlates variance runs"
    )
    assert re.search(r"\bunless\b", clause, re.IGNORECASE), (
        "the repeat-run clause is not stated as conditional"
    )
