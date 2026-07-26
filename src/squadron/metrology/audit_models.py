"""The audit oracle's typed surface — one import site for 323's shapes.

Mirrors ``report_models.py`` (321) and ``calibration_models.py`` (322):
Pydantic models, not console text, so ``--json`` emits them verbatim.

Every shape here is defined in ``models.py`` and re-exported. That is the
322 layering correction applied transitively: ``AuditRun`` and
``AuditNoiseFloor`` are ``MetrologyRecord`` envelope payloads and must live
beside the envelope, and because they embed ``AuditFinding``, ``FloorStat``,
and the enums, defining *those* here would invert the dependency and
reintroduce the circular import the correction removed.

Two separations encoded in those definitions must not be collapsed:

``AuditSeverity`` is the audit's own ``critical/high/medium/low`` scale and
is **never** mapped onto ``review.models.Severity``
(``PASS/NOTE/CONCERN/FAIL``). The two vocabularies grade different things on
different artifacts; a mapping would manufacture an equivalence that does
not exist. ``tests/metrology/test_audit_models.py`` asserts they stay
disjoint.

``AuditCategory`` is closed, and ``OTHER`` is load-bearing rather than a
dumping ground — an out-of-vocabulary category is retained on
``AuditFinding.raw_category``, never dropped.
"""

from __future__ import annotations

from squadron.metrology.models import (
    AuditCategory,
    AuditEffort,
    AuditFinding,
    AuditNoiseFloor,
    AuditRun,
    AuditSeverity,
    FloorStat,
)

__all__ = [
    "AuditCategory",
    "AuditEffort",
    "AuditFinding",
    "AuditNoiseFloor",
    "AuditRun",
    "AuditSeverity",
    "FloorStat",
]
