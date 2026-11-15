"""The measured sample-count estimate a grade run ends with (slice 425 D15).

Built from the same matrix the report reads, so the estimate and the report include the same
cases. It is a pure function of the stored grades, so it is recomputed and overwritten each
run. When nothing can be estimated nothing is written, and the note says which condition
failed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from squadron.benchmark.grade_deps import GradeDeps
from squadron.benchmark.grade_matrix import build_matrix
from squadron.benchmark.paired_stats import (
    MIN_COMPARED_CONFIGS,
    MIN_PAIRED_CASES,
    MIN_SAMPLES_FOR_VARIANCE,
    estimate_sample_count,
)
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.grade_records import SampleSizeEstimate


@dataclass(frozen=True)
class EstimateInputs:
    """What the estimate reads that the grade run itself does not hold."""

    run: BenchmarkRun
    case_ids: Sequence[str]
    replays: Sequence[tuple[str, ImplementationReplay]]
    target_difference: float


def write_estimate(inputs: EstimateInputs, deps: GradeDeps, now: datetime) -> str:
    """Write the benchmark's one estimate and return a line saying so, or why not."""
    run = inputs.run
    matrix = build_matrix(
        case_ids=inputs.case_ids,
        samples=run.samples,
        replays=inputs.replays,
        grades=[grade for _, grade in deps.store.grades_for(run.benchmark_id)],
        grader_digest=deps.grader.digest,
        reference_for=lambda case_id, digest: deps.store.get_reference_grade(
            case_id, deps.grader.digest, digest
        ),
    )
    if run.samples < MIN_SAMPLES_FOR_VARIANCE:
        return (
            f"no sample-count estimate: {run.samples} sample per case, "
            f"at least {MIN_SAMPLES_FOR_VARIANCE} needed"
        )
    if len(matrix.comparable_rows) < MIN_COMPARED_CONFIGS:
        return "no sample-count estimate: it needs two configs to compare"
    if len(matrix.included_cases) < MIN_PAIRED_CASES:
        return (
            f"no sample-count estimate: {len(matrix.included_cases)} included cases, "
            f"at least {MIN_PAIRED_CASES} needed"
        )
    pairs = estimate_sample_count(matrix.pass_samples(), inputs.target_difference)
    if not pairs:
        return "no sample-count estimate: no config pair has enough graded cases"
    deps.store.write_estimate(
        SampleSizeEstimate(
            benchmark_id=run.benchmark_id,
            case_set=run.case_set,
            case_set_version=run.case_set_version,
            grader_digest=deps.grader.digest,
            n_cases=len(matrix.included_cases),
            samples=run.samples,
            pairs=pairs,
            created_at=now,
        )
    )
    return (
        f"sample-count estimate written: {len(pairs)} pair(s), "
        f"{len(matrix.included_cases)} cases, {run.samples} samples"
    )
