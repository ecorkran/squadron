"""Run loop resume: reruns, orphan outputs, retry, write failure (slice 430 D8)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.recipe import Recipe
from squadron.benchmark.recall.run_bound import build_run_bound
from squadron.benchmark.recall.run_loop import LoopResult, LoopStatus, live_loop_deps, run_pending
from squadron.benchmark.recall.run_plan import PendingStage, expand_pending
from squadron.benchmark.recall.stage_runner import stage_paths
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.recall_run_models import RecallRun, StageKind, StageOutcome
from squadron.metrology.store import MetrologyStore
from tests.benchmark.recall.scoring_support import make_case
from tests.benchmark.recall.stage_support import (
    FakeSandboxes,
    StubLeakChecker,
    live_config_for,
    output_arg,
    review_document,
    sq_finding,
    stage_deps,
    write_json,
    writing_runner,
)
from tests.benchmark.recall.support import FIXED_NOW
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed

CASE = make_case()
#: The sandbox an earlier, crashed invocation ran the call in (not this run's sandbox).
EARLIER_SANDBOX = Path("/tmp/recall-earlier-invocation/sandbox")
RECIPE = Recipe(name="r", reviewers=("rev",))


class FailingOnceStore(RecallRecordStore):
    """A store whose next ``put_run`` raises, as a full disk would."""

    fail_next = False

    def put_run(self, run: RecallRun) -> None:
        if self.fail_next:
            self.fail_next = False
            raise MetrologyStoreError("disk full")
        super().put_run(run)


def _store(tmp_path: Path) -> FailingOnceStore:
    return FailingOnceStore(MetrologyStore(tmp_path / "store"), clock=lambda: FIXED_NOW)


def _pending(store: RecallRecordStore, retry: bool = False) -> list[PendingStage]:
    runs = {(r.case_id, r.run_index): r for r in store.list_runs()}
    return expand_pending([RECIPE], [CASE], [1], runs, live_config_for, retry_harness=retry)


def _loop(
    tmp_path: Path,
    store: RecallRecordStore,
    runner: ScriptedRunner,
    leak: StubLeakChecker | None = None,
    retry: bool = False,
) -> LoopResult:
    pending = _pending(store, retry)
    bound = build_run_bound(pending, [], 10.0, 0.01, None, lambda profile: True)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(exist_ok=True)
    deps = live_loop_deps(store, FakeSandboxes(sandbox), stage_deps(tmp_path, runner, leak=leak), None)
    return run_pending(bound, deps)


def _ok_runner() -> ScriptedRunner:
    return writing_runner(
        lambda call: write_json(output_arg(call.argv), review_document([sq_finding(1)]))
    )


def _never() -> ScriptedRunner:
    def handler(call: RunnerCall) -> object:
        raise AssertionError(f"no call expected: {call.argv}")

    return ScriptedRunner(handler)  # type: ignore[arg-type]


def test_rerun_of_a_complete_plan_dispatches_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert _loop(tmp_path, store, _ok_runner()).stored == 1
    assert _pending(store) == []
    assert _loop(tmp_path, store, _never()).stored == 0


def _write_orphan(tmp_path: Path, keep_home: bool) -> PendingStage:
    stage = _pending(_store(tmp_path))[0]
    paths = stage_paths(stage, tmp_path / "bench")
    paths.output.parent.mkdir(parents=True)
    write_json(paths.output, review_document([sq_finding(1), sq_finding(2)]))
    paths.sandbox_record.write_text(str(EARLIER_SANDBOX))
    if keep_home:
        paths.home.mkdir(parents=True)
    return stage


def test_orphan_with_home_present_is_ingested_and_scanned(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    _write_orphan(tmp_path, keep_home=True)
    leak = StubLeakChecker()
    with caplog.at_level(logging.WARNING):
        result = _loop(tmp_path, store, _never(), leak=leak)
    assert result.status is LoopStatus.COMPLETE and result.stored == 1
    assert len(leak.seen) == 1
    assert leak.seen[0].sandbox == EARLIER_SANDBOX  # the tree the crashed call ran in
    entry = next(iter(store.get_run(CASE.case_id, 1).reviews.values()))  # type: ignore[union-attr]
    assert len(entry.findings) == 2
    assert any("ingested an output file with no entry" in r.getMessage() for r in caplog.records)


def test_orphan_with_home_gone_is_repeated_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    _write_orphan(tmp_path, keep_home=False)
    runner = _ok_runner()
    with caplog.at_level(logging.WARNING):
        _loop(tmp_path, store, runner)
    assert len(runner.calls) == 1
    assert any(
        r.levelno == logging.WARNING and "cost was spent without a record" in r.getMessage()
        for r in caplog.records
    )
    entry = next(iter(store.get_run(CASE.case_id, 1).reviews.values()))  # type: ignore[union-attr]
    assert len(entry.findings) == 1  # the repeated call's output, not the orphan's


def test_retry_supersedes_and_deletes_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    no_file = writing_runner(lambda call: None, lambda call: failed(call.argv, code=2, stderr="quota"))
    _loop(tmp_path, store, no_file)
    first = next(iter(store.get_run(CASE.case_id, 1).reviews.values()))  # type: ignore[union-attr]
    assert first.outcome is StageOutcome.HARNESS_FAILURE
    assert _pending(store) == []  # not retried without the flag
    _loop(tmp_path, store, _ok_runner(), retry=True)
    run = store.get_run(CASE.case_id, 1)
    assert run is not None
    current = next(iter(run.reviews.values()))
    assert current.outcome is StageOutcome.OK
    assert run.superseded == [first]


def test_write_failure_stops_with_error_and_next_run_ingests(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    store.fail_next = True
    with caplog.at_level(logging.ERROR):
        result = _loop(tmp_path, store, _ok_runner())
    assert result.status is LoopStatus.ERROR and "disk full" in str(result.reason)
    assert any(
        r.levelno == logging.ERROR and "output file kept" in r.getMessage() for r in caplog.records
    )
    stage = _pending(store)[0]
    assert stage_paths(stage, tmp_path / "bench").output.is_file()
    assert store.list_runs() == []
    again = _loop(tmp_path, store, _never())
    assert again.status is LoopStatus.COMPLETE and again.stored == 1
    entry = next(iter(store.get_run(CASE.case_id, 1).reviews.values()))  # type: ignore[union-attr]
    assert json.loads(store.reviews.get(entry.raw_ref or ""))["findings"][0]["title"] == "finding 1"


def test_a_retry_stopped_after_the_review_leaves_its_combs_pending(tmp_path: Path) -> None:
    store = _store(tmp_path)
    recipe = Recipe(name="rc", reviewers=("rev",), combs=("comber",))
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    def loop(runner: ScriptedRunner, retry: bool, budget: ReviewBudget | None) -> LoopResult:
        runs = {(r.case_id, r.run_index): r for r in store.list_runs()}
        pending = expand_pending([recipe], [CASE], [1], runs, live_config_for, retry_harness=retry)
        bound = build_run_bound(pending, [], 10.0, 0.01, None, lambda profile: True)
        deps = live_loop_deps(store, FakeSandboxes(sandbox), stage_deps(tmp_path, runner), budget)
        return run_pending(bound, deps)

    no_file = writing_runner(lambda call: None, lambda call: failed(call.argv, code=2, stderr="quota"))
    loop(no_file, retry=False, budget=None)  # failed review, then an empty comb (no call)
    old = store.get_run(CASE.case_id, 1)
    assert old is not None and len(old.combs) == 1
    capped = loop(_ok_runner(), retry=True, budget=ReviewBudget(cap_usd=0.000001, per_review_usd=0.01))
    assert capped.status is LoopStatus.CAPPED
    run = store.get_run(CASE.case_id, 1)
    assert run is not None and run.combs == {}
    assert [e.kind for e in run.superseded] == [StageKind.REVIEW, StageKind.COMB]
    runs = {(CASE.case_id, 1): run}
    next_plan = expand_pending([recipe], [CASE], [1], runs, live_config_for)
    assert [(p.kind, p.replaces) for p in next_plan] == [(StageKind.COMB, None)]
