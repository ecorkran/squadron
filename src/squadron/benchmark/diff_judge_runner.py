"""Running a judge plan: lock, bound, over-size records, cap, resume (slice 426 D14-D16).

The lock is the judge's own, ``<benchmark root>/<benchmark_id>.judge.lock``, apart from the
run's and the grade's. The bound prints before the first call. A pair already recorded under
the same judge is not in the plan (resume is a lookup by id). A run that reaches its cap keeps
every record already written and says so.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from squadron.benchmark.bench_lock import LOCK_SUFFIX, BenchmarkLock
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.diff_judge import (
    DiffJudgmentWriter,
    DiffSidecarWriter,
    JudgeContext,
    JudgeSummary,
    judge_case,
)
from squadron.benchmark.diff_judge_budget import JudgeBudget, JudgeCapReached, metered
from squadron.benchmark.diff_judge_plan import JudgeHalted, JudgePlan, JudgeRefusal, render_bound
from squadron.benchmark.diff_pairs import Contestant, Pair
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_case_models import DiffJudgment, OverSizeCase
from squadron.replay.judging import JudgeDispatcher

_logger = logging.getLogger(__name__)

JUDGE_LOCK_SUFFIX = ".judge"
EXIT_CAP_REACHED = 2


class JudgeStatus(StrEnum):
    COMPLETE = "complete"
    CAP_REACHED = "cap_reached"


class JudgeStore(DiffJudgmentWriter, Protocol):
    def write_over_size_case(self, over_size: OverSizeCase) -> str: ...


@dataclass(frozen=True)
class JudgeRunResult:
    status: JudgeStatus
    summary: JudgeSummary
    over_size: int
    harness_absent: int
    spent_usd: float
    unpriced_calls: int


def judge_lock_path(root: Path, benchmark_id: str) -> Path:
    """Where the judge lock for *benchmark_id* lives."""
    return root / f"{benchmark_id}{JUDGE_LOCK_SUFFIX}{LOCK_SUFFIX}"


def pair_line(pair: Pair, judgment: DiffJudgment) -> str:
    """``case-… opus s1 vs sol s1: A``, or ``… forfeit B``; the reference has no sample."""
    outcome = judgment.outcome.value if judgment.outcome is not None else "?"
    kind = f"forfeit {outcome}" if judgment.forfeit else outcome
    return f"{judgment.case_id} {_side(pair.a)} vs {_side(pair.b)}: {kind}"


def _side(contestant: Contestant) -> str:
    return contestant.label if contestant.sample is None else f"{contestant.label} s{contestant.sample}"


def run_judging(
    plan: JudgePlan,
    *,
    store: JudgeStore,
    sidecars: DiffSidecarWriter,
    dispatcher: JudgeDispatcher,
    timeout_s: float,
    lock_root: Path,
    process_runner: ProcessRunner,
    print_line: Callable[[str], None],
    clock: Callable[[], datetime],
) -> JudgeRunResult:
    """Judge every pair *plan* names; the bound prints first and the lock is held throughout.

    Raises ``JudgeRefusal`` while another invocation judges the same benchmark, and
    ``JudgeHalted`` when a record cannot be stored.
    """
    path = judge_lock_path(lock_root, plan.benchmark_id)
    try:
        lock = BenchmarkLock.acquire(
            lock_root, f"{plan.benchmark_id}{JUDGE_LOCK_SUFFIX}", process_runner
        )
    except BenchmarkRefusal as exc:
        _logger.warning("judge lock %s is held: %s", path, exc)
        raise JudgeRefusal(f"{exc} (lock {path})") from exc
    with lock:
        print_line(render_bound(plan))
        budget = JudgeBudget(plan.run_cap_usd, plan.per_call_usd)
        _write_over_size(plan, store, clock)
        context = JudgeContext(
            benchmark_id=plan.benchmark_id,
            judge=plan.judge.ref,
            dispatcher=metered(dispatcher, budget),
            timeout_s=timeout_s,
            sidecars=sidecars,
            store=store,
            limit=plan.limit,
            before_call=budget.check,
            clock=clock,
        )
        summary = JudgeSummary()
        status = asyncio.run(_judge_all(plan, context, summary, print_line))
        return JudgeRunResult(
            status=status,
            summary=summary,
            over_size=len(plan.over_size),
            harness_absent=len(plan.harness_absent),
            spent_usd=budget.spent_usd,
            unpriced_calls=budget.unpriced_calls,
        )


def _write_over_size(plan: JudgePlan, store: JudgeStore, clock: Callable[[], datetime]) -> None:
    """One record per over-size case, replaced when the limit moves; a failure halts the run."""
    for case, over in plan.over_size:
        record = OverSizeCase(
            benchmark_id=plan.benchmark_id,
            case_id=case.case_id,
            judge=plan.judge.ref,
            longest_prompt_chars=over.longest_chars,
            longest_contestant=over.contestant,
            max_prompt_chars=plan.limit,
            created_at=clock(),
        )
        try:
            store.write_over_size_case(record)
        except MetrologyStoreError as exc:
            _logger.exception("could not record over-size case %s", case.case_id)
            raise JudgeHalted(f"could not record over-size case {case.case_id}: {exc}") from exc


async def _judge_all(
    plan: JudgePlan,
    context: JudgeContext,
    summary: JudgeSummary,
    print_line: Callable[[str], None],
) -> JudgeStatus:
    def show(pair: Pair, judgment: DiffJudgment) -> None:
        print_line(pair_line(pair, judgment))

    try:
        for case_plan in plan.cases:
            await judge_case(case_plan.case, case_plan.pairs, context, summary, on_judgment=show)
    except JudgeCapReached as reached:
        print_line(f"stopped: {reached}")
        return JudgeStatus.CAP_REACHED
    except MetrologyStoreError as exc:
        _logger.exception("could not record a judgment")
        raise JudgeHalted(f"could not record a judgment: {exc}") from exc
    return JudgeStatus.COMPLETE


def summary_lines(plan: JudgePlan, result: JudgeRunResult) -> list[str]:
    """The counts after the per-pair lines."""
    summary = result.summary
    lines = [
        f"judged {summary.judged} pairs, {summary.forfeits} forfeits, {summary.failed} failed; "
        f"over size {result.over_size}, harness-absent {result.harness_absent}",
        f"spent ${result.spent_usd:.2f} of run cap ${plan.run_cap_usd:.2f}; "
        f"{result.unpriced_calls} calls reported no cost and were counted at "
        f"${plan.per_call_usd:.2f} each",
    ]
    if summary.failed:
        lines.append("failed pairs are not recorded; rerun to retry them")
    if result.status is JudgeStatus.CAP_REACHED:
        lines.append("stopped at the run cap; rerun with a larger --max-cost to continue")
    return lines
