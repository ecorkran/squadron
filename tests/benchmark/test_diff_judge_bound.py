"""The printed bound and the run cap (slice 426, Task 33)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from squadron.benchmark.diff_judge_budget import JudgeBudget, JudgeCapReached, metered
from squadron.benchmark.diff_judge_plan import render_bound
from squadron.benchmark.diff_judge_runner import JudgeStatus, run_judging, summary_lines
from squadron.core.process_runner import SubprocessRunner
from squadron.replay.judging import JudgeReply
from tests.benchmark.diff_judge_run_support import (
    NOW,
    PER_CALL,
    ScriptedDispatcher,
    World,
    make_world,
    plan_of,
    run_plan,
)


def _world(tmp_path: Path, k: int = 1) -> World:
    return make_world(tmp_path, cases={"a": {"opus": k, "sol": k}, "b": {"opus": k, "sol": k}})


def test_the_bound_arithmetic_on_a_hand_computed_plan(tmp_path: Path) -> None:
    # Two cases, two configs at k = 1: 1 cross + 2 reference pairs each = 6 pairs, 12 calls.
    plan = plan_of(_world(tmp_path), max_cost=0.30, judge_cost=0.04)

    assert (plan.pairs, plan.forfeits, plan.calls) == (6, 0, 12)
    text = render_bound(plan)
    assert "pairs 6 (0 forfeits) → 12 calls × $0.04 (--judge-cost) = $0.48" in text
    assert "capped at run cap $0.30" in text
    assert "+ one call of overshoot $0.04 → at most $0.34" in text
    assert "no per-call cap" in text


def test_a_plan_under_the_cap_says_so(tmp_path: Path) -> None:
    text = render_bound(plan_of(_world(tmp_path), max_cost=8.0, judge_cost=0.04))

    assert "= $0.48, under run cap $8.00" in text
    assert "overshoot" not in text


def test_the_bound_prints_the_per_call_figure_unrounded(tmp_path: Path) -> None:
    # 12 calls × $0.035 = $0.42: rounding the figure to cents would read as 12 × $0.04 = $0.48.
    text = render_bound(plan_of(_world(tmp_path), max_cost=8.0, judge_cost=0.035))

    assert "12 calls × $0.035 (--judge-cost) = $0.42, under run cap $8.00" in text


def test_the_overshoot_line_prints_the_figure_unrounded(tmp_path: Path) -> None:
    text = render_bound(plan_of(_world(tmp_path), max_cost=0.10, judge_cost=0.035))

    assert "one call of overshoot $0.035 → at most $0.14" in text


def test_the_bound_opens_with_the_judge_limit_and_counts(tmp_path: Path) -> None:
    text = render_bound(plan_of(_world(tmp_path)))

    first, second = text.splitlines()[:2]
    assert first == "judge bench-3f9c0a1b2c3d4e5f  judge gpt-judge (openai-oauth)  limit 400000 chars"
    assert second == "slice cases 2: 2 to judge · 0 over size · 0 harness-absent"


def test_an_empty_plan_says_nothing_to_judge(tmp_path: Path) -> None:
    world = _world(tmp_path)
    run_plan(world, plan_of(world), ScriptedDispatcher(), lock_root=tmp_path / "locks")

    assert render_bound(plan_of(world)).endswith("nothing to judge")


def test_the_bound_is_printed_before_the_first_dispatch(tmp_path: Path) -> None:
    world = _world(tmp_path)
    dispatcher = ScriptedDispatcher()
    order: list[str] = []
    original = dispatcher.__call__

    async def watched(prompt: str) -> JudgeReply:
        order.append("dispatch")
        return await original(prompt)

    lines: list[str] = []
    run_judging(
        plan_of(world),
        store=world.store,
        sidecars=world.sidecars,
        dispatcher=watched,
        timeout_s=5.0,
        lock_root=tmp_path / "locks",
        process_runner=SubprocessRunner(),
        print_line=lambda line: (order.append("line"), lines.append(line))[1],
        clock=lambda: NOW,
    )

    assert order[0] == "line" and lines[0].startswith("judge bench-")
    assert order.index("dispatch") > order.index("line")


def test_the_cap_stops_after_the_call_that_crosses_it_and_keeps_earlier_records(
    tmp_path: Path,
) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=0.10, judge_cost=PER_CALL)  # room for 2.5 calls
    dispatcher = ScriptedDispatcher(cost=PER_CALL)

    result, lines = run_plan(world, plan, dispatcher, lock_root=tmp_path / "locks")

    assert result.status is JudgeStatus.CAP_REACHED
    assert len(dispatcher.prompts) == 3  # the third call crossed $0.10 and was the last
    assert result.spent_usd == pytest.approx(0.12)
    assert result.summary.judged == 1  # the first pair has both calls
    assert len(world.store.diff_judgments_for(world.run.benchmark_id)) == 1
    assert any(line.startswith("stopped: run cap reached") for line in lines)


def test_an_unpriced_call_counts_at_the_figure(tmp_path: Path) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=0.10, judge_cost=0.04)

    result, _ = run_plan(world, plan, ScriptedDispatcher(cost=None), lock_root=tmp_path / "locks")

    assert result.status is JudgeStatus.CAP_REACHED
    assert result.unpriced_calls == 3
    assert result.spent_usd == pytest.approx(0.12)
    assert any("3 calls reported no cost" in line for line in summary_lines(plan, result))


def test_a_failed_call_is_charged_at_the_figure(tmp_path: Path) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=5.0, judge_cost=PER_CALL)

    result, _ = run_plan(
        world, plan, ScriptedDispatcher(cost=PER_CALL, fail_calls={1}), lock_root=tmp_path / "locks"
    )

    # 12 calls planned; the first failed, so its pair stopped: 11 dispatched, all counted.
    assert result.summary.failed == 1
    assert result.unpriced_calls == 1
    assert result.spent_usd == pytest.approx(11 * PER_CALL)


def test_a_timed_out_call_is_charged_at_the_figure() -> None:
    budget = JudgeBudget(cap_usd=1.0, per_call_usd=PER_CALL)
    hung = metered(ScriptedDispatcher(hang_calls={1}), budget)

    with pytest.raises(TimeoutError):
        asyncio.run(asyncio.wait_for(hung("prompt"), timeout=0.05))

    assert budget.unpriced_calls == 1
    assert budget.spent_usd == pytest.approx(PER_CALL)


def test_the_budget_refuses_only_when_nothing_is_left() -> None:
    budget = JudgeBudget(cap_usd=0.05, per_call_usd=0.04)
    budget.check()
    budget.spent_usd = 0.049
    budget.check()
    budget.spent_usd = 0.05

    with pytest.raises(JudgeCapReached):
        budget.check()
