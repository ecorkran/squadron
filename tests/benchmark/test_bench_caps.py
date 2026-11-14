"""Caps, the plan and the stated bound (slice 424 Task 23)."""

from __future__ import annotations

import hashlib
import math

import pytest

from squadron.benchmark.bench_plan import (
    DISPATCH_BOUNDED_PROFILES,
    BenchConfig,
    BenchmarkPlan,
    BenchmarkRefusal,
    Caps,
    build_plan,
    format_bound,
    resolve_caps,
)
from squadron.config.keys import COST_CAP_KEY

OPUS = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
SOL = BenchConfig("sol", "sol-model", "openai-oauth", None)
# Real case ids are sha-derived; low-entropy ids would collide in the 12-digit segment.
CASE_IDS = [f"case-{hashlib.sha256(str(n).encode()).hexdigest()[:16]}" for n in range(10)]
CAPS = Caps(run_cap_usd=40.0, per_replay_cap_usd=1.5, per_replay_source="--max-cost-per-replay")
NO_UNPRICED: frozenset[str] = frozenset()


def _plan(
    configs: list[BenchConfig], recorded: int = 0, case_ids: list[str] = CASE_IDS
) -> BenchmarkPlan:
    everything = build_plan(
        set_name="fixes",
        set_version=2,
        case_ids=case_ids,
        configs=configs,
        samples=3,
        existing_record_ids=(),
    )
    done = [r.record_id for r in everything.replays[:recorded]]
    return build_plan(
        set_name="fixes",
        set_version=2,
        case_ids=case_ids,
        configs=configs,
        samples=3,
        existing_record_ids=done,
    )


class TestResolveCaps:
    def test_run_cap_missing_names_the_flag(self) -> None:
        with pytest.raises(BenchmarkRefusal, match="--max-cost "):
            resolve_caps(None, 1.0, None)

    def test_per_replay_cap_with_neither_source_names_the_flag_and_key(self) -> None:
        with pytest.raises(BenchmarkRefusal) as raised:
            resolve_caps(40.0, None, None)
        assert "--max-cost-per-replay" in str(raised.value)
        assert COST_CAP_KEY == "pipeline.max_cost_usd"
        assert COST_CAP_KEY in str(raised.value)

    @pytest.mark.parametrize("bad", [0, -1.0, True, math.nan, math.inf, "2"])
    def test_invalid_run_cap_refuses(self, bad: object) -> None:
        with pytest.raises(BenchmarkRefusal, match="--max-cost must be a positive number"):
            resolve_caps(bad, 1.0, None)

    @pytest.mark.parametrize("bad", [0, -1.0, True, math.nan, "2"])
    def test_invalid_per_replay_flag_refuses(self, bad: object) -> None:
        with pytest.raises(BenchmarkRefusal, match="--max-cost-per-replay must be a positive"):
            resolve_caps(40.0, bad, None)

    @pytest.mark.parametrize("bad", [0, -1.0, True, math.nan])
    def test_invalid_config_cap_refuses_naming_the_key(self, bad: object) -> None:
        with pytest.raises(BenchmarkRefusal, match=f"{COST_CAP_KEY} must be a positive"):
            resolve_caps(40.0, None, bad)

    def test_flag_beats_config(self) -> None:
        caps = resolve_caps(40.0, 2.0, 9.0)
        assert (caps.per_replay_cap_usd, caps.per_replay_source) == (2.0, "--max-cost-per-replay")

    def test_config_is_used_when_there_is_no_flag(self) -> None:
        caps = resolve_caps(40, None, 1.5)
        assert (caps.run_cap_usd, caps.per_replay_cap_usd) == (40.0, 1.5)
        assert caps.per_replay_source == COST_CAP_KEY

    def test_a_bad_config_value_is_ignored_when_the_flag_is_set(self) -> None:
        assert resolve_caps(40.0, 2.0, "junk").per_replay_cap_usd == 2.0


class TestBuildPlan:
    def test_order_is_case_major_then_sample_then_config(self) -> None:
        plan = _plan([OPUS, SOL], case_ids=CASE_IDS[:2])
        order = [(r.case_id, r.sample, r.config.alias) for r in plan.replays]
        assert order[:7] == [
            (CASE_IDS[0], 0, "opus"),
            (CASE_IDS[0], 0, "sol"),
            (CASE_IDS[0], 1, "opus"),
            (CASE_IDS[0], 1, "sol"),
            (CASE_IDS[0], 2, "opus"),
            (CASE_IDS[0], 2, "sol"),
            (CASE_IDS[1], 0, "opus"),
        ]
        assert len(plan.replays) == 12

    def test_recorded_replays_are_not_pending(self) -> None:
        plan = _plan([OPUS, SOL], recorded=6)
        assert (len(plan.replays), len(plan.pending), plan.recorded) == (60, 54, 6)
        assert plan.pending[0].case_id == CASE_IDS[1]


class TestFormatBound:
    def _bound(self, plan: BenchmarkPlan, unpriced: frozenset[str] = NO_UNPRICED) -> str:
        return format_bound(plan, CAPS, DISPATCH_BOUNDED_PROFILES, unpriced)

    def test_the_design_example_matches_exactly(self) -> None:
        plan = _plan([OPUS, SOL], recorded=6)
        assert self._bound(plan) == (
            f"benchmark {plan.benchmark_id}  set fixes v2  configs opus, sol  samples 3\n"
            "pending 54 of 60 replays (6 already recorded)\n"
            "bound: 27 × $1.50 per replay = $40.50, capped at run cap $40.00\n"
            "       + one replay of overshoot $1.50 → at most $41.50 for opus\n"
            "       not bounded: sol (openai-oauth) — cost is checked only after each dispatch"
        )

    def test_headline_below_the_run_cap_is_not_inflated(self) -> None:
        plan = _plan([OPUS], case_ids=CASE_IDS[:2])
        text = self._bound(plan)
        assert "bound: 6 × $1.50 per replay = $9.00, within run cap $40.00" in text
        assert "at most $10.50 for opus" in text

    def test_all_unbounded_plan_has_no_headline_figure(self) -> None:
        plan = _plan([SOL])
        text = self._bound(plan)
        assert "×" not in text
        assert "bound: no pending replay is capped inside the dispatch" in text
        assert "not bounded: sol (openai-oauth) — cost is checked only after each dispatch" in text

    def test_fully_recorded_plan_prints_pending_zero(self) -> None:
        plan = _plan([OPUS, SOL], recorded=60)
        text = self._bound(plan)
        assert "pending 0 of 60 replays (60 already recorded)" in text
        assert "bound: nothing to run" in text
        assert "×" not in text

    def test_config_with_no_reported_cost_is_not_bounded_with_that_reason(self) -> None:
        plan = _plan([OPUS, SOL])
        text = self._bound(plan, unpriced=frozenset({"opus"}))
        assert "not bounded: opus (sdk) — reports no cost" in text
        assert "not bounded: sol (openai-oauth) — cost is checked only after each dispatch" in text
        assert "×" not in text

    def test_bounded_configs_are_counted_by_their_pending_replays_only(self) -> None:
        plan = _plan([OPUS, SOL], recorded=2)
        assert "bound: 29 × $1.50" in self._bound(plan)

    def test_config_with_no_profile_is_not_bounded(self) -> None:
        plan = _plan([BenchConfig("odd", "m", None, None)], case_ids=CASE_IDS[:1])
        assert "not bounded: odd (None)" in self._bound(plan)

    def test_dispatch_bounded_profiles_hold_sdk(self) -> None:
        assert DISPATCH_BOUNDED_PROFILES == ("sdk",)
