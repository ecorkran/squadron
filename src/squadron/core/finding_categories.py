"""The closed finding-category vocabularies, a leaf module (slice 402, D1, D2).

Both ``squadron.review`` (write-time normalization) and ``squadron.metrology`` (audit
parsing, ingest) need these enums. They live here, importing nothing but ``enum``, so
neither package has to import the other to get them. ``squadron.metrology.models`` and
``squadron.metrology.audit_models`` re-export ``AuditCategory`` for existing imports.
"""

from __future__ import annotations

from enum import StrEnum


class AuditCategory(StrEnum):
    """The closed issue-class vocabulary audit findings normalize into (323).

    Nine values mirror the audit skill's nine prose dimensions; ``OTHER`` is
    the tenth and is **load-bearing, not a dumping ground**. A finding whose
    category the model invents outside this vocabulary normalizes to
    ``OTHER`` with its original string retained on
    ``AuditFinding.raw_category`` — nothing is discarded. A rising ``other``
    share is evidence the vocabulary does not fit a codebase, which the
    baseline report surfaces rather than hides.

    The skill file enumerates these same ten values. That duplication spans
    a process boundary (a markdown prompt and a Python enum cannot import
    from each other) and is held in sync by
    ``tests/metrology/test_audit_skill_sync.py``, so drift fails CI.
    """

    ARCHITECTURAL_DECAY = "architectural-decay"
    CONSISTENCY_ROT = "consistency-rot"
    TYPE_CONTRACT_DEBT = "type-contract-debt"
    TEST_DEBT = "test-debt"
    DEPENDENCY_CONFIG_DEBT = "dependency-config-debt"
    PERFORMANCE_RESOURCE = "performance-resource"
    ERROR_HANDLING_OBSERVABILITY = "error-handling-observability"
    SECURITY_HYGIENE = "security-hygiene"
    DOCUMENTATION_DRIFT = "documentation-drift"
    OTHER = "other"


class ReviewCategory(StrEnum):
    """The closed category vocabulary code-review findings normalize into (402).

    The ten ``AuditCategory`` members with identical names and values, plus
    ``CORRECTNESS``. ``correctness`` is review-only: the audit's tech-debt taxonomy
    has no slot for "this code behaves wrongly", which is a code review's main
    output, and adding it to ``AuditCategory`` would change the vocabulary the audit
    parser and noise floor are built on. ``tests/metrology/test_review_category_sync.py``
    keeps this enum, the audit skill and the ``code`` template in step.
    """

    ARCHITECTURAL_DECAY = AuditCategory.ARCHITECTURAL_DECAY.value
    CONSISTENCY_ROT = AuditCategory.CONSISTENCY_ROT.value
    TYPE_CONTRACT_DEBT = AuditCategory.TYPE_CONTRACT_DEBT.value
    TEST_DEBT = AuditCategory.TEST_DEBT.value
    DEPENDENCY_CONFIG_DEBT = AuditCategory.DEPENDENCY_CONFIG_DEBT.value
    PERFORMANCE_RESOURCE = AuditCategory.PERFORMANCE_RESOURCE.value
    ERROR_HANDLING_OBSERVABILITY = AuditCategory.ERROR_HANDLING_OBSERVABILITY.value
    SECURITY_HYGIENE = AuditCategory.SECURITY_HYGIENE.value
    DOCUMENTATION_DRIFT = AuditCategory.DOCUMENTATION_DRIFT.value
    OTHER = AuditCategory.OTHER.value
    CORRECTNESS = "correctness"
