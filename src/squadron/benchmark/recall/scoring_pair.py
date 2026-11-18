"""Score one (case, run) of a row: bug hits in both bounds and finding counts (D3, D5). Pure."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from squadron.benchmark.recall.hit_rule import HitOutcome, resolve
from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.scoring import ReviewerOutput
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import FindingGrade
from squadron.metrology.recall_run_models import RecallFinding


@dataclass
class PairScore:
    """Counts for one (case, run) over the given reviewers' kept findings."""

    case: RealBugCase
    run_index: int
    hit_low: set[str] = field(default_factory=set[str])
    hit_high: set[str] = field(default_factory=set[str])
    findings: int = 0
    matched_nothing: int = 0
    adjacent: int = 0
    undecided_candidates: int = 0
    undecided_comb: int = 0
    #: Grades of graded lower-bound findings from imported entries, with their labeler.
    grades: list[tuple[FindingGrade, str]] = field(default_factory=list[tuple[FindingGrade, str]])
    ungraded: int = 0
    person_checked: int = 0
    person_agree: int = 0

    @property
    def bug_count(self) -> int:
        return len(self.case.bugs)

    @property
    def undecided(self) -> int:
        return self.undecided_candidates + self.undecided_comb


def score_pair(
    case: RealBugCase, run_index: int, reviewers: tuple[ReviewerOutput, ...], labels: ResolvedLabels
) -> PairScore:
    score = PairScore(case=case, run_index=run_index)
    for reviewer in reviewers:
        imported = not any(entry.is_live for entry in reviewer.entries)
        lower_ids = {f.finding_id for f in reviewer.lower}
        for finding in reviewer.upper:
            outcomes = {bug.id: resolve(finding, bug, labels) for bug in case.bugs}
            in_lower = finding.finding_id in lower_ids
            _count_upper(score, outcomes)
            if in_lower:
                _count_lower(score, finding, outcomes, labels, imported)
        score.undecided_comb += reviewer.undecided_comb
    return score


def _count_upper(score: PairScore, outcomes: dict[str, HitOutcome]) -> None:
    for bug_id, outcome in outcomes.items():
        if outcome in (HitOutcome.HIT, HitOutcome.UNDECIDED):
            score.hit_high.add(bug_id)


def _count_lower(
    score: PairScore,
    finding: RecallFinding,
    outcomes: dict[str, HitOutcome],
    labels: ResolvedLabels,
    imported: bool,
) -> None:
    score.findings += 1
    counts = Counter(outcomes.values())
    score.hit_low.update(bug_id for bug_id, o in outcomes.items() if o is HitOutcome.HIT)
    score.adjacent += counts[HitOutcome.ADJACENT]
    score.undecided_candidates += counts[HitOutcome.UNDECIDED]
    if not counts[HitOutcome.UNDECIDED] and not (counts[HitOutcome.HIT] or counts[HitOutcome.ADJACENT]):
        score.matched_nothing += 1
    _count_grade(score, finding.content_key, labels, imported)


def _count_grade(score: PairScore, key: str, labels: ResolvedLabels, imported: bool) -> None:
    """D5: grades come from the imported passes and person overrides; live entries are ungraded."""
    grade = labels.grades.get(key) if imported else None
    if grade is None:
        score.ungraded += 1
        return
    score.grades.append((grade, labels.grade_labeler[key]))
    person = labels.person_grades.get(key)
    imported_grade = labels.import_grades.get(key)
    if person is not None and imported_grade is not None:
        score.person_checked += 1
        score.person_agree += person is imported_grade
