"""Import the committed person grade overrides as ``person:results-section-12`` labels (D10).

The file is a YAML list of ``{case, issue, grade, reason}``. Each entry sets ``grade`` on
every content key that is a member of, or matched to, ``issue`` in any grading pass of the
case. One ``RecallLabels`` is written per case; an unknown case or issue is skipped and
listed with a WARNING.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from squadron.benchmark.recall.hand_run_labels import PassLabels
from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import FindingGrade, LabelerKind, RecallLabels, labeler_name

#: Repo-relative path of the committed overrides file.
OVERRIDES_PATH = Path("project-documents/user/reference/review-recall-overrides.yaml")
OVERRIDES_LABELER = labeler_name(LabelerKind.PERSON, "results-section-12")


class GradeOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case: str
    issue: str
    grade: FindingGrade
    reason: str


def load_overrides(path: Path) -> list[GradeOverride]:
    """The entries of *path*; an unreadable or malformed file raises ``ValueError``."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"overrides file {path} unreadable: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError(f"overrides file {path} is not a YAML list")
    try:
        return [GradeOverride.model_validate(item) for item in cast(list[object], raw)]
    except ValidationError as exc:
        raise ValueError(f"overrides file {path} has a bad entry: {exc}") from exc


def plan_overrides(
    path: Path, cases: dict[str, RealBugCase], labels: PassLabels, plan: ImportPlan
) -> None:
    """Add one person label record per case with an applicable override."""
    try:
        overrides = load_overrides(path)
    except ValueError as exc:
        plan.skip(str(path), str(exc))
        return
    by_name = {case.name: case for case in cases.values()}
    grades: dict[str, dict[str, FindingGrade]] = defaultdict(dict)
    notes: dict[str, list[str]] = defaultdict(list)
    for override in overrides:
        item = f"{path.name} {override.case} {override.issue}"
        if override.case not in by_name:
            plan.skip(item, f"no case named {override.case!r}")
            continue
        keys = labels.issue_keys(override.case, override.issue)
        if not keys:
            plan.skip(item, f"issue {override.issue!r} has no imported finding in case {override.case}")
            continue
        grades[override.case].update(dict.fromkeys(sorted(keys), override.grade))
        notes[override.case].append(f"{override.issue} {override.grade}: {override.reason}")
    for case_name, case_grades in grades.items():
        _add_record(by_name[case_name], case_grades, notes[case_name], plan)


def _add_record(
    case: RealBugCase, grades: dict[str, FindingGrade], notes: list[str], plan: ImportPlan
) -> None:
    passes = [label.updated for label in plan.labels.values() if label.case_id == case.case_id]
    if not passes:
        raise ValueError(f"override for {case.name} has no imported pass to date it from")
    record = RecallLabels(
        case_id=case.case_id,
        labeler=OVERRIDES_LABELER,
        labeler_kind=LabelerKind.PERSON,
        grades=grades,
        # The adjudication follows the passes it overrides; dated from them so a second
        # import builds the same record.
        updated=max(passes),
        notes="\n".join(notes),
    )
    plan.labels[record.record_id] = record
