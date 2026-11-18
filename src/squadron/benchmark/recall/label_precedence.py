"""One effective hit label and grade per finding from a case's label records (D3, D5).

Precedence: a ``person`` labeler beats every ``import:`` labeler; among ``person`` labelers
the record with the newest ``updated`` wins. Among ``import:`` labelers the import's merge
rule already left one value, so their order does not matter.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from squadron.metrology.recall_label_models import FindingGrade, HitVerdict, LabelerKind, RecallLabels


@dataclass(frozen=True)
class ResolvedLabels:
    """The winning values for one case, plus what the report needs about where grades came from."""

    hits: dict[str, dict[str, HitVerdict]] = field(default_factory=dict[str, dict[str, HitVerdict]])
    grades: dict[str, FindingGrade] = field(default_factory=dict[str, FindingGrade])
    #: The labeler whose grade won, per content key.
    grade_labeler: dict[str, str] = field(default_factory=dict[str, str])
    #: The import grade per content key, whether or not a person overrode it.
    import_grades: dict[str, FindingGrade] = field(default_factory=dict[str, FindingGrade])
    #: The labeler of each import grade.
    import_labeler: dict[str, str] = field(default_factory=dict[str, str])
    #: The winning person grade per content key.
    person_grades: dict[str, FindingGrade] = field(default_factory=dict[str, FindingGrade])

    def hit(self, content_key: str, bug_id: str) -> HitVerdict | None:
        return self.hits.get(content_key, {}).get(bug_id)


def resolve_labels(records: Iterable[RecallLabels]) -> ResolvedLabels:
    """Merge one case's label records by precedence."""
    records = list(records)
    imports = sorted(
        (r for r in records if r.labeler_kind is LabelerKind.IMPORT), key=lambda r: r.labeler
    )
    persons = sorted(
        (r for r in records if r.labeler_kind is LabelerKind.PERSON),
        key=lambda r: (r.updated, r.labeler),
    )
    resolved = ResolvedLabels()
    for record in imports:
        for key, grade in record.grades.items():
            resolved.import_grades[key] = grade
            resolved.import_labeler[key] = record.labeler
    for record in persons:
        resolved.person_grades.update(record.grades)
    # Apply import first, then persons oldest to newest, so the newest person wins last.
    for record in [*imports, *persons]:
        for key, bugs in record.hits.items():
            resolved.hits.setdefault(key, {}).update(bugs)
        for key, grade in record.grades.items():
            resolved.grades[key] = grade
            resolved.grade_labeler[key] = record.labeler
    return resolved
