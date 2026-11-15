"""Paired per-case statistics for the benchmark report (slice 425 D14, D15).

Pure functions: no I/O, no store, no model. A case is the unit of difficulty, so configs are
compared on paired per-case differences, never on samples pooled across cases. 427 imports
``bootstrap_mean_interval`` for its recall intervals, so it takes plain floats.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadron.benchmark.separability import z_total
from squadron.metrology.grade_models import PairVerdict
from squadron.metrology.grade_records import CasesNeeded, PairEstimate

BOOTSTRAP_RESAMPLES = 10_000
MIN_PAIRED_CASES = 5
#: Samples per case the estimate projects the cases needed for (D15).
PROJECTED_SAMPLE_COUNTS = (1, 2, 3, 5)
#: Samples per case a within-case variance needs (D15); one sample has no spread.
MIN_SAMPLES_FOR_VARIANCE = 2
#: A comparison needs two configs.
MIN_COMPARED_CONFIGS = 2
#: The percentile interval is the central 95%: 2.5% cut from each tail.
INTERVAL_TAIL = 0.025
_SEED_BYTES = 8
_SEED_SEPARATOR = "\0"


@dataclass(frozen=True)
class PairComparison:
    """One config pair over *n* cases: the mean difference and, with enough cases, its interval."""

    n: int
    mean: float
    low: float | None
    high: float | None
    verdict: PairVerdict


def case_pass_fraction(samples: Sequence[bool]) -> float:
    """Passes over k for one (case, config). A config absence is passed in as ``False``."""
    if not samples:
        raise ValueError("a case has at least one sample")
    return sum(samples) / len(samples)


def paired_differences(a: Mapping[str, float], b: Mapping[str, float]) -> list[float]:
    """``a - b`` per case, in case-id order. Both must cover the same cases."""
    if a.keys() != b.keys():
        only = sorted(set(a) ^ set(b))
        raise ValueError(f"the two configs cover different cases: {only}")
    return [a[case_id] - b[case_id] for case_id in sorted(a)]


def pair_seed(benchmark_id: str, key_a: str, key_b: str) -> int:
    """A seed that depends only on the benchmark and the pair, not on the order given.

    The first 8 bytes of the sha256 of the benchmark id and the two config identity strings in
    sorted order. Never ``hash()``, which is salted per process.
    """
    text = _SEED_SEPARATOR.join([benchmark_id, *sorted([key_a, key_b])])
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:_SEED_BYTES], "big")


def bootstrap_mean_interval(values: Sequence[float], seed: int) -> tuple[float, float]:
    """The percentile 95% interval of the mean of *values* over resampled cases.

    ``BOOTSTRAP_RESAMPLES`` resamples with replacement, drawn from a ``random.Random`` seeded
    with *seed* alone, so the same values and seed always give the same interval.
    """
    if not values:
        raise ValueError("an interval needs at least one value")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(math.fsum(rng.choices(values, k=n)) / n for _ in range(BOOTSTRAP_RESAMPLES))
    low = means[int(INTERVAL_TAIL * BOOTSTRAP_RESAMPLES)]
    high = means[math.ceil((1 - INTERVAL_TAIL) * BOOTSTRAP_RESAMPLES) - 1]
    return low, high


def compare_pair(differences: Sequence[float], seed: int) -> PairComparison:
    """Judge one pair from its per-case differences (D14).

    Fewer than ``MIN_PAIRED_CASES`` cases is ``too_few_cases`` with no interval. An interval
    that contains zero is ``not_distinguishable``; otherwise the sign of the mean says who leads.
    """
    n = len(differences)
    mean = math.fsum(differences) / n if n else 0.0
    if n < MIN_PAIRED_CASES:
        return PairComparison(n, mean, None, None, PairVerdict.TOO_FEW_CASES)
    low, high = bootstrap_mean_interval(differences, seed)
    if low <= 0 <= high:
        return PairComparison(n, mean, low, high, PairVerdict.NOT_DISTINGUISHABLE)
    verdict = PairVerdict.A_AHEAD if mean > 0 else PairVerdict.B_AHEAD
    return PairComparison(n, mean, low, high, verdict)


#: Pass outcomes by config key, then case id: one boolean per sample (a config absence is False).
PerCaseSamples = Mapping[str, Mapping[str, Sequence[bool]]]


def _within_case_variance(samples: Mapping[str, Sequence[bool]], case_ids: Sequence[str]) -> float:
    """The pooled sample variance of pass outcomes within a case: the mean over cases."""
    variances = [statistics.variance([float(outcome) for outcome in samples[c]]) for c in case_ids]
    return math.fsum(variances) / len(variances)


def _samples_per_case(
    per_case_samples: PerCaseSamples, keys: Sequence[str], case_ids: Sequence[str]
) -> int:
    counts = {len(per_case_samples[key][case_id]) for key in keys for case_id in case_ids}
    if len(counts) != 1:
        raise ValueError(f"cases have differing sample counts: {sorted(counts)}")
    return counts.pop()


def _pair_estimate(
    per_case_samples: PerCaseSamples,
    key_a: str,
    key_b: str,
    case_ids: Sequence[str],
    k: int,
    z: float,
    target_difference: float,
) -> PairEstimate:
    within = _within_case_variance(per_case_samples[key_a], case_ids) + _within_case_variance(
        per_case_samples[key_b], case_ids
    )
    means_a = [case_pass_fraction(per_case_samples[key_a][c]) for c in case_ids]
    means_b = [case_pass_fraction(per_case_samples[key_b][c]) for c in case_ids]
    differences = [a - b for a, b in zip(means_a, means_b, strict=True)]
    between = max(0.0, statistics.variance(differences) - within / k)

    def variance_at(samples: int) -> float:
        return between + within / samples

    needed = tuple(
        CasesNeeded(
            samples=samples,
            cases=max(MIN_PAIRED_CASES, math.ceil(z**2 * variance_at(samples) / target_difference**2)),
        )
        for samples in PROJECTED_SAMPLE_COUNTS
    )
    return PairEstimate(
        config_a=key_a,
        config_b=key_b,
        within_case_variance=within,
        between_case_variance=between,
        mdd_now=z * math.sqrt(variance_at(k) / len(case_ids)),
        cases_needed=needed,
    )


def estimate_sample_count(
    per_case_samples: PerCaseSamples, target_difference: float
) -> tuple[PairEstimate, ...]:
    """The measured variance of each config pair and the cases it implies (D15).

    For every pair with at least two samples per case and ``MIN_PAIRED_CASES`` cases in common:
    ``sigma_w`` is the within-case variance summed over the two configs, ``sigma_b`` is the
    between-case variance of the mean difference less ``sigma_w / k`` (floored at zero), and the
    minimum detectable difference is ``(z_975 + z_80) * sqrt((sigma_b + sigma_w / k) / n)``.
    Zero total variance gives MDD 0 and ``MIN_PAIRED_CASES`` cases. A pair that does not meet
    the conditions is left out, so an input with none returns an empty tuple.
    """
    if not 0 < target_difference < 1:
        raise ValueError(f"target difference must be between 0 and 1, got {target_difference}")
    z = z_total()
    estimates: list[PairEstimate] = []
    for key_a, key_b in itertools.combinations(sorted(per_case_samples), 2):
        case_ids = sorted(set(per_case_samples[key_a]) & set(per_case_samples[key_b]))
        if len(case_ids) < MIN_PAIRED_CASES:
            continue
        k = _samples_per_case(per_case_samples, (key_a, key_b), case_ids)
        if k < MIN_SAMPLES_FOR_VARIANCE:
            continue
        estimates.append(
            _pair_estimate(per_case_samples, key_a, key_b, case_ids, k, z, target_difference)
        )
    return tuple(estimates)
