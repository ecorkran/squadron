"""Benchmark identity and record ids (slice 424 D4).

A benchmark is identified by what it measures: the case set and its version, the set of
producer configs, and the sample count. Caps are deliberately not part of it, so a run that
stopped at a cap resumes under the same id with a larger one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Iterable, Sequence
from dataclasses import asdict, dataclass

from squadron.config.keys import COST_CAP_KEY
from squadron.metrology.benchmark_models import CASE_ID_PREFIX
from squadron.metrology.benchmark_replay_models import REPLAY_ID_PREFIX
from squadron.pipeline.run_spend import positive_usd
from squadron.providers.base import ProfileName

BENCHMARK_ID_PREFIX = "bench-"
BENCHMARK_ID_HEX_DIGITS = 16
#: Hex digits of the benchmark id and of the case id that a replay record id carries.
BENCHMARK_SEGMENT_DIGITS = 12
CASE_SEGMENT_DIGITS = 12
CONFIG_SEGMENT_DIGITS = 8


RUN_CAP_FLAG = "--max-cost"
PER_REPLAY_CAP_FLAG = "--max-cost-per-replay"
#: Profiles whose replays are capped inside the dispatch (slice 424 D9). Defined once.
DISPATCH_BOUNDED_PROFILES: tuple[str, ...] = (ProfileName.SDK.value,)
REASON_CHECKED_AFTER_DISPATCH = "cost is checked only after each dispatch"
REASON_REPORTS_NO_COST = "reports no cost"
_BOUND_INDENT = " " * len("bound: ")


class BenchmarkRefusal(ValueError):
    """The benchmark will not start; the message says why and what sets it right."""


class ReplayIdError(ValueError):
    """An id is too short or lacks the prefix a record id is built from."""


@dataclass(frozen=True)
class BenchConfig:
    """One producer config as the benchmark identifies it."""

    alias: str
    model: str
    profile: str | None
    #: The effort the alias is configured with, ``None`` when it sets none.
    effort_configured: str | None


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_key(config: BenchConfig) -> str:
    """Canonical JSON of the config's four fields."""
    return _canonical_json(asdict(config))


def benchmark_id(set_name: str, set_version: int, config_keys: Iterable[str], samples: int) -> str:
    """``bench-`` plus 16 hex digits over (set name, set version, sorted config keys, samples)."""
    identity = [set_name, set_version, sorted(config_keys), samples]
    return BENCHMARK_ID_PREFIX + _sha256_hex(_canonical_json(identity))[:BENCHMARK_ID_HEX_DIGITS]


def _segment(identifier: str, prefix: str, digits: int, what: str) -> str:
    start = len(prefix)
    if not identifier.startswith(prefix) or len(identifier) < start + digits:
        raise ReplayIdError(
            f"{what} {identifier!r} must start with '{prefix}' and hold at least {digits} "
            f"characters after it to build a replay record id"
        )
    return identifier[start : start + digits]


def replay_record_id(benchmark: str, case_id: str, key: str, sample: int) -> str:
    """``implreplay-<benchmark 12>-<case 12>-<config hash 8>-s<sample>``."""
    parts = (
        _segment(benchmark, BENCHMARK_ID_PREFIX, BENCHMARK_SEGMENT_DIGITS, "benchmark id"),
        _segment(case_id, CASE_ID_PREFIX, CASE_SEGMENT_DIGITS, "case id"),
        _sha256_hex(key)[:CONFIG_SEGMENT_DIGITS],
    )
    return f"{REPLAY_ID_PREFIX}{'-'.join(parts)}-s{sample}"


@dataclass(frozen=True)
class Caps:
    run_cap_usd: float
    per_replay_cap_usd: float
    #: The flag or config key the per-replay cap came from.
    per_replay_source: str


def _cap_value(value: object, source: str) -> float:
    try:
        return positive_usd(value, source)
    except ValueError as exc:
        raise BenchmarkRefusal(str(exc)) from exc


def resolve_caps(run_cap_flag: object, per_replay_flag: object, config_cap: object) -> Caps:
    """Both caps, or a refusal naming the missing cap and what sets it.

    The run cap is the flag only: a benchmark's total is decided for each invocation, so it
    has no config default. The per-replay cap is its flag, else the harness config's
    ``COST_CAP_KEY`` value.
    """
    if run_cap_flag is None:
        raise BenchmarkRefusal(
            f"no run cap: set {RUN_CAP_FLAG} USD (a benchmark's total is decided for each "
            f"invocation, so it has no config default)"
        )
    run_cap = _cap_value(run_cap_flag, RUN_CAP_FLAG)
    if per_replay_flag is not None:
        return Caps(run_cap, _cap_value(per_replay_flag, PER_REPLAY_CAP_FLAG), PER_REPLAY_CAP_FLAG)
    if config_cap is None:
        raise BenchmarkRefusal(
            f"no per-replay cap: set {PER_REPLAY_CAP_FLAG} USD or the config key {COST_CAP_KEY}"
        )
    return Caps(run_cap, _cap_value(config_cap, COST_CAP_KEY), COST_CAP_KEY)


@dataclass(frozen=True)
class PlannedReplay:
    case_id: str
    sample: int
    config: BenchConfig
    record_id: str


@dataclass(frozen=True)
class BenchmarkPlan:
    benchmark_id: str
    set_name: str
    set_version: int
    configs: tuple[BenchConfig, ...]
    samples: int
    #: Every replay of the benchmark, case-major, then sample, then config.
    replays: tuple[PlannedReplay, ...]
    #: The replays without a record yet, in the same order.
    pending: tuple[PlannedReplay, ...]

    @property
    def recorded(self) -> int:
        return len(self.replays) - len(self.pending)


def build_plan(
    *,
    set_name: str,
    set_version: int,
    case_ids: Sequence[str],
    configs: Sequence[BenchConfig],
    samples: int,
    existing_record_ids: Collection[str],
    only_cases: Collection[str] | None = None,
) -> BenchmarkPlan:
    """The benchmark's replays in schedule order; a replay with a record is not pending.

    ``only_cases`` (``--case``) limits the plan to those cases for debugging. It does not
    change the benchmark id, so the records it makes count toward the full benchmark; a case
    id that is not in the set is a refusal.
    """
    if only_cases is not None:
        unknown = sorted(set(only_cases) - set(case_ids))
        if unknown:
            raise BenchmarkRefusal(f"--case names cases that are not in the set: {', '.join(unknown)}")
        case_ids = [case_id for case_id in case_ids if case_id in only_cases]
    keys = [config_key(config) for config in configs]
    identifier = benchmark_id(set_name, set_version, keys, samples)
    replays = tuple(
        PlannedReplay(case_id, sample, config, replay_record_id(identifier, case_id, key, sample))
        for case_id in case_ids
        for sample in range(samples)
        for config, key in zip(configs, keys, strict=True)
    )
    pending = tuple(r for r in replays if r.record_id not in existing_record_ids)
    return BenchmarkPlan(identifier, set_name, set_version, tuple(configs), samples, replays, pending)


def _dollars(amount: float) -> str:
    return f"${amount:.2f}"


def _unbounded_reason(
    config: BenchConfig, bounded_profiles: Collection[str], unpriced_aliases: Collection[str]
) -> str | None:
    """Why *config*'s replays are not capped inside the dispatch, ``None`` when they are."""
    if config.alias in unpriced_aliases:
        return REASON_REPORTS_NO_COST
    if config.profile not in bounded_profiles:
        return REASON_CHECKED_AFTER_DISPATCH
    return None


def format_bound(
    plan: BenchmarkPlan,
    caps: Caps,
    bounded_profiles: Collection[str],
    unpriced_aliases: Collection[str],
) -> str:
    """The stated bound (D8), printed before the first dispatch.

    The headline covers only configs capped inside the dispatch; every other config is
    listed under ``not bounded`` with its reason. Its replays still count toward the run cap.
    """
    reasons = {c.alias: _unbounded_reason(c, bounded_profiles, unpriced_aliases) for c in plan.configs}
    bounded = [alias for alias, reason in reasons.items() if reason is None]
    bounded_pending = sum(1 for r in plan.pending if reasons[r.config.alias] is None)
    lines = [
        f"benchmark {plan.benchmark_id}  set {plan.set_name} v{plan.set_version}  "
        f"configs {', '.join(c.alias for c in plan.configs)}  samples {plan.samples}",
        f"pending {len(plan.pending)} of {len(plan.replays)} replays "
        f"({plan.recorded} already recorded)",
    ]
    if not plan.pending:
        return "\n".join([*lines, "bound: nothing to run"])
    per_replay = _dollars(caps.per_replay_cap_usd)
    if bounded_pending:
        total = bounded_pending * caps.per_replay_cap_usd
        at_most = min(total, caps.run_cap_usd) + caps.per_replay_cap_usd
        # "capped" only when the cap actually cuts the total.
        relation = "capped at" if total > caps.run_cap_usd else "within"
        lines += [
            f"bound: {bounded_pending} × {per_replay} per replay = {_dollars(total)}, "
            f"{relation} run cap {_dollars(caps.run_cap_usd)}",
            f"{_BOUND_INDENT}+ one replay of overshoot {per_replay} → at most "
            f"{_dollars(at_most)} for {', '.join(bounded)}",
        ]
    else:
        lines.append("bound: no pending replay is capped inside the dispatch")
    for config in plan.configs:
        if (reason := reasons[config.alias]) is not None:
            lines.append(f"{_BOUND_INDENT}not bounded: {config.alias} ({config.profile}) — {reason}")
    return "\n".join(lines)
