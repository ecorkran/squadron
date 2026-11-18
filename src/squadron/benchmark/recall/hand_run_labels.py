"""Import part 3: the four grading passes as import label records (D3, D5, D10).

Each pass is one labeler, ``import:<brief>``, with one ``RecallLabels`` per case it graded.
A finding ref ``<config>/<run>/<index>`` resolves to the imported finding's content key. An
issue whose ``known`` is ``Bn`` gives its members ``HIT`` for Bn (and ``MISS`` for the
case's other bugs: the grader sorted them into Bn's issue); members of other issues get
``MISS`` for every bug. When two assignments disagree, the later pass in ``GRADING_PASSES``
order wins, and the earlier value is removed so only one import value remains.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from squadron.benchmark.recall.import_plan import ImportPlan, LabelConflict, folder_date
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import (
    FindingGrade,
    HitVerdict,
    LabelerKind,
    RecallLabels,
    labeler_name,
)

PRECISION_FOLDER = "precision"


@dataclass(frozen=True)
class GradingPass:
    brief: str
    folder: str
    suffix: str

    @property
    def labeler(self) -> str:
        return labeler_name(LabelerKind.IMPORT, self.brief)

    def files(self, results_dir: Path) -> list[Path]:
        return sorted((results_dir / self.folder / PRECISION_FOLDER).glob(f"*-{self.suffix}.json"))

    def case_of(self, path: Path) -> str:
        return path.name.removesuffix(f"-{self.suffix}.json")


#: D10's pass table, in merge order: a later pass wins a conflict.
GRADING_PASSES = (
    GradingPass("grid2/BRIEF.md", "20261112-grid2", "graded"),
    GradingPass("grid3/BRIEF.md", "20261113-grid3", "graded"),
    GradingPass("grid3/BRIEF-B2.md", "20261113-grid3", "graded-b2"),
    GradingPass("grid3/BRIEF-SOL.md", "20261113-grid3", "graded-sol"),
)


@dataclass(frozen=True)
class _Issue:
    grade: FindingGrade
    known: str | None


@dataclass
class _CaseLabels:
    """Per case: each labeler's grades and hits, and each issue's content keys."""

    grades: dict[str, dict[str, FindingGrade]] = field(default_factory=lambda: defaultdict(dict))
    hits: dict[str, dict[str, dict[str, HitVerdict]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(dict))
    )
    issue_keys: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    graded_by: set[str] = field(default_factory=set[str])


@dataclass
class PassLabels:
    """The import labels by case name, kept for the overrides step."""

    by_case: dict[str, _CaseLabels] = field(default_factory=dict[str, _CaseLabels])

    def issue_keys(self, case_name: str, issue_id: str) -> set[str]:
        found = self.by_case.get(case_name)
        return set() if found is None else set(found.issue_keys.get(issue_id, set()))


def plan_labels(results_dir: Path, cases: dict[str, RealBugCase], plan: ImportPlan) -> PassLabels:
    """Fill ``plan.labels`` with one record per (pass, graded case); *cases* by hand-run id."""
    documents = _load_documents(results_dir, cases, plan)
    finding_keys = _finding_keys(plan)
    labels = PassLabels()
    for hand_id, by_pass in documents.items():
        case = cases[hand_id]
        issues = _issue_registry(by_pass, plan, case.name)
        state = labels.by_case.setdefault(case.name, _CaseLabels())
        for grading_pass in GRADING_PASSES:
            document = by_pass.get(grading_pass.labeler)
            if document is None:
                continue
            state.graded_by.add(grading_pass.labeler)
            for ref, issue_id in _assignments(document):
                key = finding_keys.get((case.case_id, *_split_ref(ref)))
                if key is None:
                    plan.skip(
                        f"{grading_pass.labeler} {hand_id} {ref}", "ref names no imported finding"
                    )
                    continue
                issue = issues.get(issue_id)
                if issue is None:
                    plan.skip(f"{grading_pass.labeler} {hand_id} {ref}", f"unknown issue {issue_id!r}")
                    continue
                state.issue_keys[issue_id].add(key)
                _assign(state, case, grading_pass.labeler, key, issue, plan)
    _emit(labels, cases, plan)
    return labels


def _load_documents(
    results_dir: Path, cases: dict[str, RealBugCase], plan: ImportPlan
) -> dict[str, dict[str, dict[str, Any]]]:
    """hand-run id -> labeler -> grade document; bad files are skipped and listed."""
    found: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for grading_pass in GRADING_PASSES:
        for path in grading_pass.files(results_dir):
            hand_id = grading_pass.case_of(path)
            if hand_id not in cases:
                plan.skip(str(path), f"no case record has hand_run_id {hand_id!r}")
                continue
            try:
                document = json.loads(path.read_bytes())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                plan.skip(str(path), f"unreadable or not valid JSON: {exc}")
                continue
            if not isinstance(document, dict):
                plan.skip(str(path), "not a JSON object")
                continue
            found[hand_id][grading_pass.labeler] = document
    return found


def _finding_keys(plan: ImportPlan) -> dict[tuple[str, str, int, int], str]:
    """(case_id, config alias, run, index) -> content key of every imported review finding."""
    keys: dict[tuple[str, str, int, int], str] = {}
    for run in plan.runs.values():
        for entry in run.reviews.values():
            for index, finding in enumerate(entry.findings):
                keys[(run.case_id, entry.alias, run.run_index, index)] = finding.content_key
    return keys


def _split_ref(ref: str) -> tuple[str, int, int]:
    """``<config>/<run>/<index>``; a malformed ref maps to a key nothing has."""
    config, run, index = (ref.rsplit("/", 2) + ["", ""])[:3]
    if not (run.isdigit() and index.isdigit()):
        return ref, -1, -1
    return config, int(run), int(index)


def _issue_list(document: dict[str, Any]) -> list[dict[str, Any]]:
    items = [*document.get("issues", []), *document.get("new_issues", [])]
    return [item for item in items if isinstance(item, dict)]


def _issue_registry(
    by_pass: dict[str, dict[str, Any]], plan: ImportPlan, case_name: str
) -> dict[str, _Issue]:
    """Every issue any pass of the case defined; a bad grade word is skipped and listed."""
    issues: dict[str, _Issue] = {}
    for labeler, document in by_pass.items():
        for item in _issue_list(document):
            try:
                grade = FindingGrade(str(item.get("grade")))
            except ValueError:
                plan.skip(
                    f"{labeler} {case_name} {item.get('id')}", f"unknown grade {item.get('grade')!r}"
                )
                continue
            known = item.get("known")
            issues[str(item.get("id"))] = _Issue(grade, known if isinstance(known, str) else None)
    return issues


def _assignments(document: dict[str, Any]) -> list[tuple[str, str]]:
    """(finding ref, issue id): issue members first, then ``matched`` refs."""
    pairs = [
        (str(ref), str(item.get("id")))
        for item in _issue_list(document)
        for ref in item.get("members", [])
    ]
    matched = document.get("matched", {})
    if isinstance(matched, dict):
        refs = cast(dict[object, object], matched)
        pairs.extend((str(ref), str(issue_id)) for ref, issue_id in refs.items())
    return pairs


def _assign(
    state: _CaseLabels, case: RealBugCase, labeler: str, key: str, issue: _Issue, plan: ImportPlan
) -> None:
    bug_ids = [bug.id for bug in case.bugs]
    if issue.known is not None and issue.known not in bug_ids:
        plan.skip(f"{labeler} {case.name} {key}", f"known bug {issue.known!r} is not a bug of the case")
        return
    _set_value(state.grades, key, labeler, issue.grade, case.name, "grade", plan)
    for bug_id in bug_ids:
        verdict = HitVerdict.HIT if bug_id == issue.known else HitVerdict.MISS
        _set_hit(state, key, bug_id, labeler, verdict, case.name, plan)


def _set_value(
    table: dict[str, dict[str, FindingGrade]],
    key: str,
    labeler: str,
    value: FindingGrade,
    case_name: str,
    what: str,
    plan: ImportPlan,
) -> None:
    for other, values in table.items():
        old = values.get(key)
        if old is not None and old != value:
            plan.conflicts.append(
                LabelConflict(case_name, key, what, f"{other}={old}", f"{labeler}={value}")
            )
            del values[key]
    table[labeler][key] = value


def _set_hit(
    state: _CaseLabels,
    key: str,
    bug_id: str,
    labeler: str,
    verdict: HitVerdict,
    case_name: str,
    plan: ImportPlan,
) -> None:
    for other, by_key in state.hits.items():
        old = by_key.get(key, {}).get(bug_id)
        if old is not None and old != verdict:
            plan.conflicts.append(
                LabelConflict(case_name, key, f"hit {bug_id}", f"{other}={old}", f"{labeler}={verdict}")
            )
            del by_key[key][bug_id]
    state.hits[labeler][key][bug_id] = verdict


def _emit(labels: PassLabels, cases: dict[str, RealBugCase], plan: ImportPlan) -> None:
    by_name = {case.name: case for case in cases.values()}
    folders = {grading_pass.labeler: grading_pass.folder for grading_pass in GRADING_PASSES}
    for case_name, state in labels.by_case.items():
        case = by_name[case_name]
        for labeler in sorted(state.graded_by):
            record = RecallLabels(
                case_id=case.case_id,
                labeler=labeler,
                labeler_kind=LabelerKind.IMPORT,
                hits={key: dict(bugs) for key, bugs in state.hits[labeler].items() if bugs},
                grades=dict(state.grades[labeler]),
                updated=folder_date(folders[labeler]),
            )
            plan.labels[record.record_id] = record
