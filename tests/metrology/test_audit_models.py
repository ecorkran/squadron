"""Audit model shapes, and the vocabulary separations that must not collapse.

The interesting assertions here are not the round-trips — they are the
disjointness check between ``AuditSeverity`` and the review system's
``Severity``, and the retention of ``raw_category``. Both encode decisions
that a later edit could plausibly and quietly undo.
"""

from __future__ import annotations

from squadron.metrology.audit_models import (
    AuditCategory,
    AuditEffort,
    AuditFinding,
    AuditNoiseFloor,
    AuditRun,
    AuditSeverity,
    FloorStat,
)
from squadron.review.models import Severity
from tests.metrology.conftest import make_audit_finding, make_audit_run, make_noise_floor


def test_audit_category_has_exactly_the_ten_values() -> None:
    """The vocabulary is closed at ten — nine dimensions plus ``other``."""
    assert {member.value for member in AuditCategory} == {
        "architectural-decay",
        "consistency-rot",
        "type-contract-debt",
        "test-debt",
        "dependency-config-debt",
        "performance-resource",
        "error-handling-observability",
        "security-hygiene",
        "documentation-drift",
        "other",
    }


def test_audit_severity_and_effort_values() -> None:
    assert {member.value for member in AuditSeverity} == {"critical", "high", "medium", "low"}
    assert {member.value for member in AuditEffort} == {"S", "M", "L"}


def test_audit_severity_is_disjoint_from_review_severity() -> None:
    """Audit severity and review severity share no value. Deliberate.

    The audit grades code debt (``critical/high/medium/low``); the review
    system grades an artifact against its source (``PASS/NOTE/CONCERN/FAIL``).
    A mapping between them would manufacture an equivalence that does not
    exist, so this asserts the two vocabularies stay separate — case-folded,
    since a future edit could plausibly re-case one side and reintroduce an
    accidental overlap.
    """
    audit_values = {member.value.casefold() for member in AuditSeverity}
    review_values = {member.value.casefold() for member in Severity}
    assert audit_values.isdisjoint(review_values)


def test_finding_round_trips_without_raw_category() -> None:
    """An in-vocabulary finding carries no ``raw_category``."""
    finding = make_audit_finding()
    assert finding.raw_category is None
    assert AuditFinding.model_validate_json(finding.model_dump_json()) == finding


def test_finding_round_trips_retaining_raw_category() -> None:
    """An out-of-vocabulary category is retained, not discarded.

    ``other`` is load-bearing: the original string survives the round-trip so
    a rising ``other`` share stays inspectable rather than becoming an
    anonymous bucket.
    """
    finding = make_audit_finding(
        category=AuditCategory.OTHER,
        raw_category="prompt-injection-surface",
    )
    restored = AuditFinding.model_validate_json(finding.model_dump_json())
    assert restored == finding
    assert restored.raw_category == "prompt-injection-surface"


def test_finding_effort_is_optional() -> None:
    finding = make_audit_finding(effort=None)
    assert AuditFinding.model_validate_json(finding.model_dump_json()).effort is None


def test_audit_run_round_trips() -> None:
    run = make_audit_run(
        findings=[make_audit_finding(finding_id="F001"), make_audit_finding(finding_id="F002")],
        unnormalized_count=2,
    )
    restored = AuditRun.model_validate_json(run.model_dump_json())
    assert restored == run
    assert len(restored.findings) == 2
    assert restored.unnormalized_count == 2


def test_noise_floor_round_trips_with_per_category_stats() -> None:
    """``per_category`` keys survive as enum members through JSON."""
    floor = make_noise_floor(
        per_category={
            AuditCategory.TEST_DEBT: FloorStat(min=0, max=4, mean=2.0, stddev=2.0),
            AuditCategory.OTHER: FloorStat(min=1, max=1, mean=1.0, stddev=0.0),
        }
    )
    restored = AuditNoiseFloor.model_validate_json(floor.model_dump_json())
    assert restored == floor
    assert restored.per_category[AuditCategory.TEST_DEBT].max == 4
