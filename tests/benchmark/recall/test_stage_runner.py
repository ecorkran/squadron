"""One stage call and its outcomes (slice 430 D6, D8). Fake runner, stub leak checker."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from squadron.benchmark.recall.recipe import Recipe
from squadron.benchmark.recall.run_plan import PendingStage, expand_pending
from squadron.benchmark.recall.scoring import recipe_outputs
from squadron.benchmark.recall.scoring_select import StageIdentity
from squadron.benchmark.recall.stage_ingest import empty_comb_entry, failure_entry
from squadron.benchmark.recall.stage_runner import run_stage, stage_paths
from squadron.core.models import Effort
from squadron.core.process_runner import ProcessNotFoundError, ProcessTimedOutError
from squadron.metrology.recall_run_models import (
    CombVerdict,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
)
from squadron.review.models import Verdict
from tests.benchmark.recall.scoring_support import StubResolver, make_case
from tests.benchmark.recall.stage_support import (
    StubLeakChecker,
    harness_env,
    live_config_for,
    output_arg,
    pending_for,
    review_document,
    sq_finding,
    stage_deps,
    write_json,
    writing_runner,
)
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed

CASE = make_case()
REVIEW_ONLY = Recipe(name="r", reviewers=("rev",))
WITH_COMB = Recipe(name="rc", reviewers=("rev",), combs=("comber",))


def _review_stage() -> PendingStage:
    return pending_for(CASE, REVIEW_ONLY)[0]


def _warned(caplog: pytest.LogCaptureFixture, *parts: str) -> bool:
    return any(
        r.levelno == logging.WARNING and all(p in r.getMessage() for p in parts) for r in caplog.records
    )


def _run(
    tmp_path: Path,
    stage: PendingStage,
    runner: ScriptedRunner,
    run: RecallRun | None = None,
    **kw: object,
) -> StageEntry:
    deps = stage_deps(tmp_path, runner, **kw)  # type: ignore[arg-type]
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(exist_ok=True)
    return run_stage(stage, run or RecallRun(case_id=CASE.case_id, run_index=1), sandbox, deps)


def _raise(error: Exception) -> ScriptedRunner:
    def handler(call: RunnerCall) -> object:
        raise error

    return ScriptedRunner(handler)  # type: ignore[arg-type]


def test_review_ok_stores_findings_and_raw_ref(tmp_path: Path) -> None:
    document = review_document([sq_finding(1), sq_finding(2, severity="NOTE")])
    runner = writing_runner(lambda call: write_json(output_arg(call.argv), document))
    stage = _review_stage()
    entry = _run(tmp_path, stage, runner)
    assert entry.outcome is StageOutcome.OK and len(entry.findings) == 2
    assert entry.effort_sent is not None and entry.effort_sent.value == "high"
    assert entry.leak is RecallLeakVerdict.CONFINED
    deps = stage_deps(tmp_path, runner)
    assert entry.raw_ref is not None and json.loads(deps.ingest.sidecar.get(entry.raw_ref)) == document
    argv = runner.calls[0].argv
    assert argv[:3] == ("/opt/sq", "review", "code") and argv[argv.index("--model") + 1] == "rev"
    assert runner.calls[0].replace_env and runner.calls[0].env is not None
    assert runner.calls[0].env["OPENROUTER_API_KEY"] == "test-key"
    assert runner.calls[0].cwd == str(tmp_path / "sandbox")


def test_subprocess_cannot_start_is_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), _raise(ProcessNotFoundError("/opt/sq")))
    assert entry.outcome is StageOutcome.HARNESS_FAILURE and "could not start" in str(
        entry.outcome_reason
    )
    assert _warned(caplog, "case demo-1", "run 1", "review rev", "harness_failure")


def test_exit_without_output_file_is_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = writing_runner(
        lambda call: None, lambda call: failed(call.argv, code=3, stderr="quota exhausted")
    )
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), runner)
    assert entry.outcome is StageOutcome.HARNESS_FAILURE
    assert "exit 3" in str(entry.outcome_reason) and "quota exhausted" in str(entry.outcome_reason)
    assert _warned(caplog, "case demo-1", "harness_failure", "exit 3")


def test_missing_credential_is_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env = harness_env(tmp_path)
    del env["OPENROUTER_API_KEY"]
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), writing_runner(lambda call: None), env=env)
    assert entry.outcome is StageOutcome.HARNESS_FAILURE
    assert _warned(caplog, "harness_failure", "OPENROUTER_API_KEY")


def test_review_timeout_is_config_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    leak = StubLeakChecker()
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), _raise(ProcessTimedOutError(["sq"], 30)), leak=leak)
    assert entry.outcome is StageOutcome.CONFIG_FAILURE and "timed out" in str(entry.outcome_reason)
    assert len(leak.seen) == 1  # the call ran, so its transcript is scanned
    assert _warned(caplog, "review rev", "config_failure", "timed out")


def test_review_output_unparseable_is_config_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = writing_runner(lambda call: output_arg(call.argv).write_text("{not json"))
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), runner)
    assert entry.outcome is StageOutcome.CONFIG_FAILURE and entry.raw_ref is not None
    assert _warned(caplog, "config_failure", "no parseable result")


def test_review_with_unknown_verdict_is_config_failure_keeping_usage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The review parser's degraded shape (UNKNOWN, no findings) is not a clean zero-finding review."""
    document = {**review_document([]), "verdict": Verdict.UNKNOWN.value}
    runner = writing_runner(lambda call: write_json(output_arg(call.argv), document))
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, _review_stage(), runner)
    assert entry.outcome is StageOutcome.CONFIG_FAILURE and entry.findings == ()
    assert entry.usage.cost_usd == 0.01 and entry.raw_ref is not None
    assert _warned(caplog, "review rev", "config_failure", "UNKNOWN")


def _comb_setup(tmp_path: Path) -> tuple[PendingStage, RecallRun]:
    """A stored live review with two CONCERNs and a NOTE, and the pending comb stage."""
    review_stage, comb_stage = pending_for(CASE, WITH_COMB)
    document = review_document([sq_finding(1), sq_finding(2, severity="NOTE"), sq_finding(3)])
    review_entry = _run(
        tmp_path, review_stage, writing_runner(lambda call: write_json(output_arg(call.argv), document))
    )
    run = RecallRun(case_id=CASE.case_id, run_index=1, reviews={review_stage.slot: review_entry})
    return comb_stage, run


def _comb_runner(raw: str) -> ScriptedRunner:
    return writing_runner(
        lambda call: write_json(output_arg(call.argv), {"raw_output": raw, "effort": None})
    )


def test_comb_input_holds_only_the_parents_kept_findings(tmp_path: Path) -> None:
    stage, run = _comb_setup(tmp_path)
    runner = _comb_runner("F1: KEEP — a\nF2: DROP — b")
    entry = _run(tmp_path, stage, runner, run)
    sent = json.loads(stage_paths(stage, tmp_path / "bench").comb_input.read_text())
    assert [f["finding_id"] for f in sent] == ["F1", "F3"]  # the NOTE is not scored
    assert entry.decisions["F1"].verdict is CombVerdict.KEEP
    assert entry.decisions["F3"].verdict is CombVerdict.DROP  # F2 in the comb call is review F3
    argv = runner.calls[0].argv
    assert (
        argv[1:4] == ("benchmark", "recall", "_stage") and argv[argv.index("--diff") + 1] == CASE.base
    )


def test_comb_timeout_is_config_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    stage, run = _comb_setup(tmp_path)
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, stage, _raise(ProcessTimedOutError(["sq"], 30)), run)
    assert entry.kind is StageKind.COMB and entry.outcome is StageOutcome.CONFIG_FAILURE
    assert _warned(caplog, "comb comber", "config_failure", "timed out")


def test_comb_output_with_no_decision_line_is_config_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    stage, run = _comb_setup(tmp_path)
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, stage, _comb_runner("I looked at everything and it is fine."), run)
    assert entry.outcome is StageOutcome.CONFIG_FAILURE
    assert _warned(caplog, "comb comber", "no parseable decision line")


def test_comb_partial_is_ok_with_undecided(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    stage, run = _comb_setup(tmp_path)
    with caplog.at_level(logging.WARNING):
        entry = _run(tmp_path, stage, _comb_runner("F1: KEEP — real"), run)
    assert entry.outcome is StageOutcome.OK
    assert entry.decisions["F3"].verdict is CombVerdict.UNDECIDED
    assert _warned(caplog, "comb comber", "decided 1 of 2")


def test_comb_with_empty_input_makes_no_call(tmp_path: Path) -> None:
    review_stage, comb_stage = pending_for(CASE, WITH_COMB)
    empty = _run(
        tmp_path,
        review_stage,
        writing_runner(lambda call: write_json(output_arg(call.argv), review_document([]))),
    )
    run = RecallRun(case_id=CASE.case_id, run_index=1, reviews={review_stage.slot: empty})
    runner = _comb_runner("unused")
    entry = _run(tmp_path, comb_stage, runner, run)
    assert entry.outcome is StageOutcome.OK and entry.decisions == {} and runner.calls == []
    assert entry.usage.cost_usd == 0.0  # no call, so a known zero, not "not recorded"


def test_failed_and_no_call_entries_keep_their_identity_and_are_scored(tmp_path: Path) -> None:
    def high(alias: str, kind: StageKind) -> tuple[StageConfig, Effort | None]:
        return live_config_for(alias, kind)[0], Effort.high

    review_stage, comb_stage = expand_pending([WITH_COMB], [CASE], [1], {}, high)
    deps = stage_deps(tmp_path, writing_runner(lambda call: None))
    failed = failure_entry(review_stage, StageOutcome.HARNESS_FAILURE, "no output", deps.ingest)
    empty = empty_comb_entry(comb_stage, deps.ingest)
    assert failed.effort_sent is Effort.high and empty.effort_sent is Effort.high
    run = RecallRun(case_id=CASE.case_id, run_index=1, reviews={review_stage.slot: failed})
    run.combs[comb_stage.slot] = empty
    resolver = StubResolver(
        {
            alias: StageIdentity(high(alias, kind)[0].config_key, Effort.high)
            for alias, kind in (("rev", StageKind.REVIEW), ("comber", StageKind.COMB))
        }
    )
    row = recipe_outputs(WITH_COMB, [CASE], {(CASE.case_id, 1): run}, [1], resolver)[0]
    assert row.dropped == {"harness": 1} and row.left_out == []
