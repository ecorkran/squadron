"""The measured line of the yield report: a graded benchmark's estimate beside the analytic bound
(slice 425 D15), split out of ``yield_report`` to keep that module under 300 lines."""

from __future__ import annotations

from dataclasses import dataclass

from squadron.benchmark.report_rows import identity_label
from squadron.metrology.grade_records import SampleSizeEstimate


@dataclass(frozen=True)
class MeasuredLine:
    """A graded benchmark's measured estimate for a case set, beside the analytic bound (425 D15).

    ``pair`` is the config pair that needs the most cases at the benchmark's k.
    """

    benchmark_id: str
    case_set: str
    n_cases: int
    samples: int
    pair: tuple[str, str]
    mdd_now: float
    #: Cases needed and the k they are projected at (the benchmark's k, or the nearest below).
    cases_needed: int
    needed_at_samples: int


def _needed_at(estimate: SampleSizeEstimate, pair_index: int) -> tuple[int, int]:
    """Cases needed at the estimate's k (or the nearest projected k below it), and that k."""
    options = sorted(estimate.pairs[pair_index].cases_needed, key=lambda item: item.samples)
    eligible = [item for item in options if item.samples <= estimate.samples]
    if not eligible:
        raise ValueError(
            f"estimate for {estimate.benchmark_id} projects no k at or below its k={estimate.samples}"
        )
    chosen = eligible[-1]
    return chosen.cases, chosen.samples


def measured_line(estimate: SampleSizeEstimate) -> MeasuredLine | None:
    """The pair needing the most cases at the estimate's k, ``None`` when it has no pairs."""
    if not estimate.pairs:
        return None
    index = max(range(len(estimate.pairs)), key=lambda i: _needed_at(estimate, i)[0])
    cases, at_samples = _needed_at(estimate, index)
    pair = estimate.pairs[index]
    return MeasuredLine(
        benchmark_id=estimate.benchmark_id,
        case_set=estimate.case_set,
        n_cases=estimate.n_cases,
        samples=estimate.samples,
        pair=(pair.config_a, pair.config_b),
        mdd_now=pair.mdd_now,
        cases_needed=cases,
        needed_at_samples=at_samples,
    )


def measured_text(line: MeasuredLine) -> str:
    first, second = (identity_label(identity) for identity in line.pair)
    return (
        f"measured ({line.benchmark_id}, n={line.n_cases}, k={line.samples}) {line.case_set}: "
        f"{first} vs {second} needs the most cases: MDD {line.mdd_now:.2f} now · "
        f"need {line.cases_needed} cases at k={line.needed_at_samples}"
    )


def measured_json(line: MeasuredLine) -> dict[str, object]:
    return {
        "benchmark_id": line.benchmark_id,
        "case_set": line.case_set,
        "n_cases": line.n_cases,
        "samples": line.samples,
        "pair": list(line.pair),
        "mdd_now": line.mdd_now,
        "cases_needed": line.cases_needed,
        "needed_at_samples": line.needed_at_samples,
    }
