"""Classifying a producer run: one test per D10 row, and the precedence between them."""

from __future__ import annotations

import pytest

from squadron.benchmark.replay_outcome import (
    STDERR_TAIL_CHARS,
    ProducerClassification,
    classify_producer_run,
)
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.fix_keys import ISSUE_SOURCE_KEY, ISSUE_TEXT_SHA256_KEY
from squadron.pipeline.state import RunState
from tests.stats.producer_support import action, prompt_identity, run, step, usage

ISSUE_SHA = "a" * 64
BEFORE, AFTER = "1" * 40, "2" * 40
RECORD_ID = "implreplay-0123456789ab-0123456789ab-01234567-s0"


def process(returncode: int = 0, stderr: str = "") -> ProcessResult:
    return ProcessResult(("sq",), returncode, "", stderr)


def fix_context(
    source: str = "file", sha: str = ISSUE_SHA, *, success: bool = True
) -> dict[str, object]:
    return action(
        "fix-context",
        success=success,
        outputs={ISSUE_SOURCE_KEY: source, ISSUE_TEXT_SHA256_KEY: sha} if success else {},
        error=None if success else "cannot read issue.md",
    )


def dispatch(**kwargs: object) -> dict[str, object]:
    kwargs.setdefault("usage_record", usage(cost=0.4, effort="high"))
    return action("dispatch", model="claude-opus", profile="sdk", **kwargs)  # type: ignore[arg-type]


def fix_run(actions: list[dict[str, object]] | None = None, *, status: str = "completed") -> RunState:
    body = actions if actions is not None else [fix_context(), dispatch(), action("commit")]
    return run(RECORD_ID, [step("fix-0", "fix", body, status=status)], pipeline="fix", status=status)


def classify(
    state: RunState | None,
    *,
    after: str = AFTER,
    result: ProcessResult | None = None,
) -> ProducerClassification:
    return classify_producer_run(result or process(), state, BEFORE, after, ISSUE_SHA)


class TestRows:
    def test_no_state_is_no_run_state_harness(self) -> None:
        result = classify(None, result=process(137, "Killed"), after=BEFORE)
        assert result.outcome == ProducerOutcome.NO_RUN_STATE
        assert result.absence == AbsenceClass.HARNESS
        assert "exited 137" in (result.failure_detail or "")
        assert "Killed" in (result.failure_detail or "")
        assert result.run_id is None

    def test_state_still_running_is_no_run_state_harness(self) -> None:
        result = classify(fix_run(status="running"), result=process(-9), after=BEFORE)
        assert (result.outcome, result.absence) == (
            ProducerOutcome.NO_RUN_STATE,
            AbsenceClass.HARNESS,
        )
        assert "still 'running'" in (result.failure_detail or "")

    def test_sha_mismatch_is_frozen_text_mismatch_harness(self) -> None:
        result = classify(fix_run([fix_context(sha="b" * 64), dispatch(), action("commit")]))
        assert (result.outcome, result.absence) == (
            ProducerOutcome.FROZEN_TEXT_MISMATCH,
            AbsenceClass.HARNESS,
        )
        assert "b" * 64 in (result.failure_detail or "")

    def test_issue_fetched_from_github_is_a_mismatch(self) -> None:
        state = fix_run([fix_context(source="github"), dispatch()])
        assert classify(state).outcome == ProducerOutcome.FROZEN_TEXT_MISMATCH

    def test_failed_fix_context_is_a_mismatch_naming_the_error(self) -> None:
        state = fix_run([fix_context(success=False)], status="failed")
        result = classify(state, after=BEFORE)
        assert result.outcome == ProducerOutcome.FROZEN_TEXT_MISMATCH
        assert "cannot read issue.md" in (result.failure_detail or "")

    def test_no_fix_context_outputs_is_a_mismatch(self) -> None:
        result = classify(fix_run([dispatch()]))
        assert result.outcome == ProducerOutcome.FROZEN_TEXT_MISMATCH
        assert "no fix-context" in (result.failure_detail or "")

    def test_cost_cap_failure_is_config(self) -> None:
        failed = dispatch(success=False, error="budget", failure_kind=FailureKind.COST_CAP.value)
        result = classify(fix_run([fix_context(), failed], status="failed"), after=BEFORE)
        assert (result.outcome, result.absence) == (ProducerOutcome.COST_CAP, AbsenceClass.CONFIG)
        assert "cost_cap" in (result.failure_detail or "")

    def test_paused_awaiting_a_human_is_blocked_config(self) -> None:
        asking = action("dispatch", success=False, error="BLOCKED: need a decision")
        asking["awaits_human"] = True
        result = classify(fix_run([fix_context(), asking], status="paused"), after=BEFORE)
        assert (result.outcome, result.absence) == (ProducerOutcome.BLOCKED, AbsenceClass.CONFIG)
        assert "need a decision" in (result.failure_detail or "")

    def test_completed_with_head_moved_is_committed_with_no_absence(self) -> None:
        result = classify(fix_run())
        assert (result.outcome, result.absence, result.failure_detail) == (
            ProducerOutcome.COMMITTED,
            None,
            None,
        )
        assert result.run_id == RECORD_ID

    def test_completed_with_head_unchanged_is_no_commit_config(self) -> None:
        result = classify(fix_run(), after=BEFORE)
        assert (result.outcome, result.absence) == (ProducerOutcome.NO_COMMIT, AbsenceClass.CONFIG)

    def test_fix_report_refusal_with_head_unchanged_is_no_commit(self) -> None:
        refusal = action(
            "commit",
            success=False,
            error="fix report is missing",
            failure_kind=FailureKind.FIX_REPORT.value,
        )
        state = fix_run([fix_context(), dispatch(), refusal], status="failed")
        result = classify(state, after=BEFORE)
        assert (result.outcome, result.absence) == (ProducerOutcome.NO_COMMIT, AbsenceClass.CONFIG)
        assert "fix_report" in (result.failure_detail or "")
        assert "fix report is missing" in (result.failure_detail or "")

    @pytest.mark.parametrize(
        "kind", [FailureKind.STALL, FailureKind.PROVIDER_ERROR, FailureKind.TOOL_ISOLATION]
    )
    def test_other_failed_runs_are_producer_failed_with_the_kind(self, kind: FailureKind) -> None:
        failed = dispatch(success=False, error="no output", failure_kind=kind.value)
        result = classify(fix_run([fix_context(), failed], status="failed"), after=BEFORE)
        assert (result.outcome, result.absence) == (
            ProducerOutcome.PRODUCER_FAILED,
            AbsenceClass.CONFIG,
        )
        assert kind.value in (result.failure_detail or "")

    def test_turn_timeout_failure_without_a_kind_is_producer_failed(self) -> None:
        failed = dispatch(success=False, error="codex turn timed out after 600s")
        result = classify(fix_run([fix_context(), failed], status="failed"), after=BEFORE)
        assert result.outcome == ProducerOutcome.PRODUCER_FAILED
        assert "codex turn timed out" in (result.failure_detail or "")

    def test_paused_for_another_reason_is_producer_failed_not_blocked(self) -> None:
        limited = dispatch(
            success=False, error="usage limit", failure_kind=FailureKind.USAGE_LIMIT.value
        )
        result = classify(fix_run([fix_context(), limited], status="paused"), after=BEFORE)
        assert result.outcome == ProducerOutcome.PRODUCER_FAILED
        assert "usage_limit" in (result.failure_detail or "")

    def test_failed_fix_report_run_with_head_moved_is_not_committed(self) -> None:
        refusal = action("commit", success=False, failure_kind=FailureKind.FIX_REPORT.value)
        result = classify(fix_run([fix_context(), refusal], status="failed"), after=AFTER)
        assert result.outcome == ProducerOutcome.PRODUCER_FAILED


class TestPrecedence:
    def test_cost_capped_run_with_mismatched_text_is_frozen_text_mismatch(self) -> None:
        capped = dispatch(success=False, error="budget", failure_kind=FailureKind.COST_CAP.value)
        state = fix_run([fix_context(sha="c" * 64), capped], status="failed")
        assert classify(state, after=BEFORE).outcome == ProducerOutcome.FROZEN_TEXT_MISMATCH

    def test_no_state_beats_everything(self) -> None:
        assert classify(None).outcome == ProducerOutcome.NO_RUN_STATE

    def test_cost_cap_beats_blocked(self) -> None:
        capped = dispatch(success=False, failure_kind=FailureKind.COST_CAP.value)
        capped["awaits_human"] = True
        state = fix_run([fix_context(), capped], status="paused")
        assert classify(state, after=BEFORE).outcome == ProducerOutcome.COST_CAP


class TestReadFromTheState:
    def test_cost_turns_effort_and_prompt_come_from_the_run(self) -> None:
        identity = prompt_identity(None)
        state = fix_run(
            [
                fix_context(),
                dispatch(prompt_identity=identity, effort_stamp="high"),
                action("commit"),
            ]
        )
        result = classify(state)
        assert result.cost_usd == pytest.approx(0.4)
        assert result.turns == 1
        assert result.effort_sent == "high"
        assert result.prompt is not None and result.prompt.sha256 == identity["sha256"]

    def test_unpriced_run_has_no_cost(self) -> None:
        state = fix_run([fix_context(), dispatch(usage_record=usage(cost=None)), action("commit")])
        assert classify(state).cost_usd is None

    def test_failure_detail_keeps_only_the_stderr_tail(self) -> None:
        noisy = "x" * (STDERR_TAIL_CHARS * 3) + "THE-CAUSE"
        result = classify(fix_run(), after=BEFORE, result=process(1, noisy))
        detail = result.failure_detail or ""
        assert detail.endswith("THE-CAUSE")
        assert len(detail) < STDERR_TAIL_CHARS + 200
