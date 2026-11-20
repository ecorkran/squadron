"""The run loop: sandboxes, serial dispatch, caps (slice 430 D7, D8, D9)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.run_bound import RunBound, build_run_bound
from squadron.benchmark.recall.run_loop import LoopDeps, LoopStatus, run_pending
from squadron.benchmark.recall.run_plan import PendingStage, expand_pending
from squadron.benchmark.recall.stage_ingest import IngestContext
from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    RecallFinding,
    RecallLeakVerdict,
    RecallRun,
    StageEntry,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import finding, make_case
from tests.benchmark.recall.stage_support import FakeSandboxes, plan_config_for
from tests.benchmark.recall.support import FIXED_NOW, fake_services

CASES = [make_case("case-a"), make_case("case-b")]
DEFAULT_FINDING = finding(1, "src/a.py")


class Recorder:
    """A stage call that records order and returns an ok entry costing *cost*.

    A review returns *findings* (one by default), so the combs after it have input.
    """

    def __init__(
        self, cost: float | None = 0.01, findings: tuple[RecallFinding, ...] = (DEFAULT_FINDING,)
    ) -> None:
        self.cost = cost
        self.findings = findings
        self.calls: list[str] = []

    def __call__(self, stage: PendingStage, run: RecallRun, sandbox: Path) -> StageEntry:
        self.calls.append(f"{stage.case.name}/{stage.run_index}/{stage.kind.value}/{stage.alias}")
        return StageEntry(
            kind=stage.kind,
            config=stage.config,
            effort_configured=stage.effort_configured,
            effort_sent=None,
            findings=self.findings if stage.kind is StageKind.REVIEW else (),
            usage=StageUsage(cost_usd=self.cost),
            outcome=StageOutcome.OK,
            leak=RecallLeakVerdict.CONFINED,
            source=LIVE_SOURCE,
            case_set="s@v1",
            alias=stage.alias,
            created=FIXED_NOW,
        )


def _ingest(tmp_path: Path) -> IngestContext:
    return IngestContext(
        ContentSidecars(tmp_path / "store", SidecarKind.REVIEWS), "s@v1", lambda: FIXED_NOW
    )


def _bound(
    recipe: Recipe,
    cases: list[RealBugCase],
    runs: list[int],
    max_cost: float = 10.0,
    plan_cap: int | None = None,
) -> RunBound:
    pending = expand_pending([recipe], cases, runs, {}, plan_config_for)
    return build_run_bound(pending, [], max_cost, 0.01, plan_cap, lambda profile: True)


def _deps(
    tmp_path: Path,
    store: RecallRecordStore,
    sandboxes: FakeSandboxes,
    call: Recorder,
    budget: ReviewBudget | None,
) -> LoopDeps:
    return LoopDeps(
        store=store,
        sandboxes=sandboxes,
        call=call,
        has_output=lambda stage: False,
        ingest_orphan=lambda stage, sandbox: None,
        remove_home=lambda stage: None,
        ingest=_ingest(tmp_path),
        budget=budget,
    )


def _store(tmp_path: Path) -> RecallRecordStore:
    return fake_services(tmp_path).store


@pytest.mark.parametrize(
    "reason",
    [
        "source repo missing: /nope",
        "sandbox build failed: git clone exited 128",
        "fetch: git fetch failed: connection reset",
        "fetch: timed out after 120s",
        "base unreachable: rev-parse failed",
    ],
)
def test_sandbox_failures_give_harness_failure_with_reason(
    tmp_path: Path, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    sandboxes = FakeSandboxes(tmp_path, failures={"case-a": reason})
    call = Recorder()
    bound = _bound(Recipe(name="r", reviewers=("a",), combs=("c",)), CASES, [1])
    with caplog.at_level(logging.WARNING):
        result = run_pending(bound, _deps(tmp_path, store, sandboxes, call, None))
    assert result.status is LoopStatus.COMPLETE
    run_a = store.get_run(CASES[0].case_id, 1)
    assert run_a is not None
    entries = [*run_a.reviews.values(), *run_a.combs.values()]
    assert len(entries) == 2 and all(e.outcome is StageOutcome.HARNESS_FAILURE for e in entries)
    assert all(reason in str(e.outcome_reason) for e in entries)
    assert any(
        r.levelno == logging.WARNING and "case case-a" in r.getMessage() and reason in r.getMessage()
        for r in caplog.records
    )
    assert call.calls == ["case-b/1/review/a", "case-b/1/comb/c"]


def test_sandbox_entered_once_per_case_and_removed(tmp_path: Path) -> None:
    sandboxes = FakeSandboxes(tmp_path)
    call = Recorder()
    bound = _bound(Recipe(name="r", reviewers=("a", "b")), CASES, [1, 2])
    run_pending(bound, _deps(tmp_path, _store(tmp_path), sandboxes, call, None))
    assert sandboxes.events == ["enter case-a", "exit case-a", "enter case-b", "exit case-b"]
    assert call.calls[:4] == [
        "case-a/1/review/a",
        "case-a/1/review/b",
        "case-a/2/review/a",
        "case-a/2/review/b",
    ]


def test_sandbox_removed_when_the_loop_stops(tmp_path: Path) -> None:
    sandboxes = FakeSandboxes(tmp_path)
    budget = ReviewBudget(cap_usd=0.015, per_review_usd=0.01)
    bound = _bound(Recipe(name="r", reviewers=("a",)), CASES, [1, 2, 3], max_cost=0.015)
    result = run_pending(bound, _deps(tmp_path, _store(tmp_path), sandboxes, Recorder(), budget))
    assert result.status is LoopStatus.CAPPED
    assert sandboxes.events == ["enter case-a", "exit case-a"]


def test_dollar_cap_stops_and_keeps_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    budget = ReviewBudget(cap_usd=0.025, per_review_usd=0.01)
    bound = _bound(Recipe(name="r", reviewers=("a",)), CASES, [1, 2, 3], max_cost=0.025)
    result = run_pending(bound, _deps(tmp_path, store, FakeSandboxes(tmp_path), Recorder(), budget))
    assert result.status is LoopStatus.CAPPED and result.stored == 3
    assert len(result.remaining) == 3
    assert sum(len(r.reviews) for r in store.list_runs()) == 3


def test_first_call_always_runs_under_a_tiny_cap(tmp_path: Path) -> None:
    budget = ReviewBudget(cap_usd=0.000001, per_review_usd=0.01)
    call = Recorder()
    bound = _bound(Recipe(name="r", reviewers=("a",)), CASES, [1], max_cost=0.000001)
    result = run_pending(
        bound, _deps(tmp_path, _store(tmp_path), FakeSandboxes(tmp_path), call, budget)
    )
    assert call.calls == ["case-a/1/review/a"]
    assert result.status is LoopStatus.CAPPED and [s.case.name for s in result.remaining] == ["case-b"]


def test_plan_cap_stops_before_the_next_plan_billed_call(tmp_path: Path) -> None:
    call = Recorder(cost=None)
    bound = _bound(Recipe(name="r", reviewers=("codex",)), CASES, [1, 2], plan_cap=3)
    assert bound.plan_billed_calls == 4
    result = run_pending(bound, _deps(tmp_path, _store(tmp_path), FakeSandboxes(tmp_path), call, None))
    assert len(call.calls) == 3
    assert result.status is LoopStatus.CAPPED and "plan-billed call cap 3" in str(result.reason)


def test_empty_comb_makes_no_call_and_spends_no_plan_cap(tmp_path: Path) -> None:
    """A comb over a review with no findings is no call, so it is neither capped nor counted."""
    call = Recorder(cost=None, findings=())
    recipe = Recipe(name="r", reviewers=("codex",), combs=("codex-comb", "codex-comb2"))
    bound = _bound(recipe, CASES[:1], [1], plan_cap=1)
    store = _store(tmp_path)
    result = run_pending(bound, _deps(tmp_path, store, FakeSandboxes(tmp_path), call, None))
    assert call.calls == ["case-a/1/review/codex"]
    assert result.status is LoopStatus.COMPLETE
    run = store.get_run(CASES[0].case_id, 1)
    assert run is not None and len(run.combs) == 2
