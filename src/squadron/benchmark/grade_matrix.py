"""Per-config, per-case outcomes of a graded benchmark, and which cases are comparable (D13).

Shared by the grade runner (the sample-count estimate) and the report, so both include exactly
the same cases. Rows are keyed by 420's D6 identity: model, profile, effort sent, ``tool_use``
and ``max_output_tokens``; the alias is a label, never a key. A case is compared only if every
config has all ``k`` samples recorded and none of them is a harness absence, from the replay or
from grading. A config absence counts as a fail.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.grade_models import GRADE_ABSENCE_CLASS
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade

_logger = logging.getLogger(__name__)

ReferenceLookup = Callable[[str, str], ReferenceGrade | None]


class Exclusion(StrEnum):
    """Why a case is not compared; the report counts cases under these values."""

    INCOMPLETE = "incomplete"
    HARNESS_REPLAY = "harness_replay"
    HARNESS_GRADE = "harness_grade"
    REFERENCE_FAILED = "reference_failed_grade"


@dataclass(frozen=True)
class RowKey:
    """A config's identity as 420 D6 states it; ``prompt`` is set only on a split row."""

    model: str
    profile: str | None
    effort_sent: str | None
    tool_use: bool | None
    max_output_tokens: int | None
    prompt: str | None = None

    @property
    def identity_text(self) -> str:
        """Canonical JSON of the identity, the string a pair's seed is derived from."""
        return json.dumps(
            [
                self.model,
                self.profile,
                self.effort_sent,
                self.tool_use,
                self.max_output_tokens,
                self.prompt,
            ]
        )


class AbsenceStage(StrEnum):
    """Where an absence happened: producing the replay, or grading it."""

    REPLAY = "replay"
    GRADE = "grade"


def absence_label(stage: AbsenceStage, kind: str) -> str:
    """The one spelling of an absence kind the report prints, ``stage:kind``."""
    return f"{stage.value}:{kind}"


@dataclass(frozen=True)
class HarnessLoss:
    """A harness absence that excludes the case: where it happened and its kind."""

    stage: AbsenceStage
    kind: str


_HARNESS_EXCLUSION = {
    AbsenceStage.REPLAY: Exclusion.HARNESS_REPLAY,
    AbsenceStage.GRADE: Exclusion.HARNESS_GRADE,
}


@dataclass(frozen=True)
class Cell:
    """One sample of one config on one case: it passed, failed, or was lost to the harness."""

    passed: bool
    #: A config absence (counted as a fail): the replay's outcome or the grade's absence.
    config_absence: str | None = None
    #: A harness absence that excludes the case, with its kind.
    harness: HarnessLoss | None = None
    #: The records the cell was read from; the report reads costs, counts and totals off them.
    replay: ImplementationReplay | None = field(default=None, compare=False)
    grade: ImplementationGrade | None = field(default=None, compare=False)


@dataclass
class GradeMatrix:
    samples: int
    #: One label (an alias) per row; never a key.
    labels: dict[RowKey, str] = field(default_factory=dict[RowKey, str])
    included_cases: tuple[str, ...] = ()
    excluded: dict[str, Exclusion] = field(default_factory=dict[str, Exclusion])
    #: Included cases only: row -> case -> cells in sample order.
    cells: dict[RowKey, dict[str, tuple[Cell, ...]]] = field(
        default_factory=dict[RowKey, dict[str, tuple[Cell, ...]]]
    )
    #: Rows whose identity spans prompt identities: shown, never merged, never compared.
    split_rows: frozenset[RowKey] = frozenset()
    warnings: tuple[str, ...] = ()
    #: Failed replays with no effort stamp, counted by failure class and given no row.
    unstamped: Counter[str] = field(default_factory=Counter[str])
    older_identity_grades: int = 0

    @property
    def comparable_rows(self) -> tuple[RowKey, ...]:
        return tuple(sorted((r for r in self.cells if r not in self.split_rows), key=_sort_key))

    def pass_samples(self) -> dict[str, dict[str, list[bool]]]:
        """Comparable rows' pass outcomes by identity text, then case id, for the estimate."""
        return {
            row.identity_text: {c: [cell.passed for cell in cells] for c, cells in by_case.items()}
            for row, by_case in self.cells.items()
            if row not in self.split_rows
        }


def _sort_key(row: RowKey) -> tuple[str, str, str, str, str, str]:
    return (
        row.model,
        row.profile or "",
        row.effort_sent or "",
        str(row.tool_use),
        str(row.max_output_tokens),
        row.prompt or "",
    )


def row_key_of(replay: ImplementationReplay) -> RowKey:
    """The row a replay belongs to: its config's identity without the prompt (420 D6)."""
    config = replay.config
    return RowKey(
        config.model, config.profile, config.effort_sent, config.tool_use, config.max_output_tokens
    )


def _cell(replay: ImplementationReplay, grade: ImplementationGrade | None) -> Cell | None:
    """The sample's cell, ``None`` when it is not graded yet."""
    if replay.absence is AbsenceClass.HARNESS:
        return Cell(
            False,
            harness=HarnessLoss(AbsenceStage.REPLAY, replay.outcome.value),
            replay=replay,
            grade=grade,
        )
    if replay.absence is AbsenceClass.CONFIG:
        return Cell(False, config_absence=replay.outcome.value, replay=replay, grade=grade)
    if grade is None:
        return None
    if grade.absence is not None:
        if GRADE_ABSENCE_CLASS[grade.absence] is AbsenceClass.HARNESS:
            return Cell(
                False,
                harness=HarnessLoss(AbsenceStage.GRADE, grade.absence.value),
                replay=replay,
                grade=grade,
            )
        return Cell(False, config_absence=grade.absence.value, replay=replay, grade=grade)
    if grade.result is None:
        raise ValueError("a grade has a result or an absence")
    return Cell(grade.result.passed, replay=replay, grade=grade)


def _reference_problem(
    case_id: str, replays: Sequence[ImplementationReplay], reference_for: ReferenceLookup
) -> bool:
    for digest in {r.environment.identity_digest for r in replays if r.environment is not None}:
        reference = reference_for(case_id, digest)
        if reference is not None and (reference.result is None or not reference.result.passed):
            return True
    return False


def build_matrix(
    *,
    case_ids: Sequence[str],
    samples: int,
    replays: Sequence[tuple[str, ImplementationReplay]],
    grades: Sequence[ImplementationGrade],
    grader_digest: str,
    reference_for: ReferenceLookup,
) -> GradeMatrix:
    """Assemble the matrix and decide, case by case, whether it is compared."""
    matrix = GradeMatrix(samples=samples)
    latest = {g.replay_id: g for g in grades if g.grader.digest == grader_digest}
    matrix.older_identity_grades = sum(g.grader.digest != grader_digest for g in grades)

    stamped: list[tuple[str, ImplementationReplay]] = []
    for record_id, replay in replays:
        if replay.config.effort_sent is None and replay.absence is not None:
            matrix.unstamped[replay.outcome.value] += 1
            continue
        stamped.append((record_id, replay))

    prompts: dict[RowKey, set[str | None]] = defaultdict(set)
    for _, replay in stamped:
        prompts[row_key_of(replay)].add(None if replay.prompt is None else replay.prompt.sha256)
    split = {identity for identity, shas in prompts.items() if len({s for s in shas if s}) > 1}
    warnings: list[str] = []
    split_rows: set[RowKey] = set()
    by_case_row: dict[str, dict[RowKey, dict[int, Cell | None]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    case_replays: dict[str, list[ImplementationReplay]] = defaultdict(list)
    for record_id, replay in stamped:
        identity = row_key_of(replay)
        row = identity
        if identity in split:
            sha = None if replay.prompt is None else replay.prompt.sha256
            row = RowKey(*_fields(identity), prompt=sha)
            split_rows.add(row)
        matrix.labels.setdefault(row, replay.config.alias)
        samples_of_row = by_case_row[replay.case_id][row]
        if replay.sample in samples_of_row:
            # Two aliases with one identity, or a record stored twice: either way a sample
            # would silently stand for two, so refuse rather than keep whichever came last.
            _logger.error("duplicate replay of %s sample %d: %s", replay.case_id, replay.sample, row)
            raise ValueError(
                f"case {replay.case_id} sample {replay.sample} of config "
                f"{matrix.labels[row]} ({row.model}) is recorded twice in one benchmark"
            )
        samples_of_row[replay.sample] = _cell(replay, latest.get(record_id))
        case_replays[replay.case_id].append(replay)
    for identity in split:
        warnings.append(
            f"{matrix.labels.get(identity, identity.model)}: replays span more than one prompt "
            f"identity; shown as separate rows, never merged or compared"
        )
    matrix.split_rows = frozenset(split_rows)
    matrix.warnings = tuple(sorted(warnings))
    _decide_inclusion(matrix, case_ids, by_case_row, case_replays, reference_for)
    return matrix


def _fields(row: RowKey) -> tuple[str, str | None, str | None, bool | None, int | None]:
    return row.model, row.profile, row.effort_sent, row.tool_use, row.max_output_tokens


def _decide_inclusion(
    matrix: GradeMatrix,
    case_ids: Sequence[str],
    by_case_row: dict[str, dict[RowKey, dict[int, Cell | None]]],
    case_replays: dict[str, list[ImplementationReplay]],
    reference_for: ReferenceLookup,
) -> None:
    identities = {RowKey(*_fields(row)) for row in matrix.labels}
    included: list[str] = []
    for case_id in sorted(case_ids):
        rows = by_case_row.get(case_id, {})
        reason = _exclusion(matrix, case_id, rows, identities, case_replays, reference_for)
        if reason is not None:
            matrix.excluded[case_id] = reason
            continue
        included.append(case_id)
        for row, by_sample in rows.items():
            matrix.cells.setdefault(row, {})[case_id] = tuple(
                cell for _, cell in sorted(by_sample.items()) if cell is not None
            )
    matrix.included_cases = tuple(included)


def _exclusion(
    matrix: GradeMatrix,
    case_id: str,
    rows: dict[RowKey, dict[int, Cell | None]],
    identities: set[RowKey],
    case_replays: dict[str, list[ImplementationReplay]],
    reference_for: ReferenceLookup,
) -> Exclusion | None:
    cells_by_identity: dict[RowKey, list[Cell | None]] = defaultdict(list)
    for row, by_sample in rows.items():
        cells_by_identity[RowKey(*_fields(row))].extend(by_sample.values())
    for identity in identities:
        cells = cells_by_identity.get(identity, [])
        if len(cells) != matrix.samples or any(cell is None for cell in cells):
            return Exclusion.INCOMPLETE
    harness = [c.harness for cells in cells_by_identity.values() for c in cells if c and c.harness]
    if harness:
        return _HARNESS_EXCLUSION[harness[0].stage]
    if _reference_problem(case_id, case_replays[case_id], reference_for):
        return Exclusion.REFERENCE_FAILED
    return None
