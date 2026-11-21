"""How a producer replay ended (slice 424 D5 state read, D10 table).

Pure over the finished ``sq`` process and the run state it left. Rows are checked top to
bottom and the first match wins. ``environment_failed`` never reaches this function: it is
decided before any producer runs. Prompt identity, effort and usage come from 177's helpers.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from squadron.benchmark.transcripts import as_mapping
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.replay_models import PromptIdentity
from squadron.pipeline.actions import ActionType
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.fix_keys import ISSUE_SOURCE_KEY, ISSUE_TEXT_SHA256_KEY, IssueSource
from squadron.pipeline.state import RUNNING_STATUS, RunState
from squadron.replay.outcome import action_failure_kind, prompt_identity
from squadron.stats.producer_units import action_metadata, effort_sent_value, first_action
from squadron.stats.usage_report import action_usage_row, usage_totals

#: How much of the child's stderr a failure detail keeps (its tail, where the cause is).
STDERR_TAIL_CHARS = 500
_AWAITS_HUMAN = "awaits_human"


@dataclass(frozen=True)
class ProducerClassification:
    outcome: ProducerOutcome
    #: ``None`` exactly when the outcome is ``committed``.
    absence: AbsenceClass | None
    failure_detail: str | None
    run_id: str | None
    cost_usd: float | None
    turns: int | None
    effort_sent: str | None
    prompt: PromptIdentity | None


_ABSENCE: dict[ProducerOutcome, AbsenceClass | None] = {
    ProducerOutcome.ENVIRONMENT_FAILED: AbsenceClass.HARNESS,
    ProducerOutcome.NO_RUN_STATE: AbsenceClass.HARNESS,
    ProducerOutcome.FROZEN_TEXT_MISMATCH: AbsenceClass.HARNESS,
    ProducerOutcome.COST_CAP: AbsenceClass.CONFIG,
    ProducerOutcome.BLOCKED: AbsenceClass.CONFIG,
    ProducerOutcome.COMMITTED: None,
    ProducerOutcome.NO_COMMIT: AbsenceClass.CONFIG,
    ProducerOutcome.PRODUCER_FAILED: AbsenceClass.CONFIG,
}


def _actions(state: RunState) -> Iterator[Mapping[str, object]]:
    for step in state.completed_steps:
        for round_actions in (*step.prior_round_results, step.action_results):
            yield from round_actions


def _stderr_tail(process: ProcessResult) -> str:
    return process.stderr.strip()[-STDERR_TAIL_CHARS:]


def _failed_kinds(state: RunState) -> list[FailureKind]:
    return [
        kind
        for action in _actions(state)
        if action.get("success") is False and (kind := action_failure_kind(action)) is not None
    ]


def _failure_error(state: RunState) -> str:
    """The first failed action's error text, ``""`` when none carries one."""
    for action in _actions(state):
        error = action.get("error")
        if action.get("success") is False and isinstance(error, str) and error:
            return error
    return ""


def _frozen_text_problem(state: RunState, issue_sha256: str) -> str | None:
    """Why the run did not use the given file, ``None`` when ``fix-context`` shows it did."""
    for action in _actions(state):
        if action.get("action_type") != ActionType.FIX_CONTEXT:
            continue
        if action.get("success") is not True:
            return f"fix-context failed: {action.get('error') or 'no error text'}"
        seen = as_mapping(action.get("outputs")) or {}
        source = seen.get(ISSUE_SOURCE_KEY)
        digest = seen.get(ISSUE_TEXT_SHA256_KEY)
        if source == IssueSource.FILE.value and digest == issue_sha256:
            return None
        return (
            f"fix-context used issue_source={source!r} sha256={digest!r}, "
            f"expected file {issue_sha256!r}"
        )
    return "the run recorded no fix-context outputs"


def awaits_human(state: RunState) -> bool:
    return state.status == ExecutionStatus.PAUSED and any(
        action.get(_AWAITS_HUMAN) is True for action in _actions(state)
    )


def _detail(label: str, state: RunState | None, process: ProcessResult) -> str:
    parts = [label]
    if state is not None and (error := _failure_error(state)):
        parts.append(error)
    if tail := _stderr_tail(process):
        parts.append(f"stderr: {tail}")
    return "; ".join(parts)


def _usage(state: RunState) -> tuple[float | None, int | None, str | None, PromptIdentity | None]:
    """Cost, turns, effort sent and prompt identity of the run's actions and first dispatch."""
    rows = [action_usage_row(state.run_id, step.step_name, a) for step in state.completed_steps
            for a in step.action_results]  # fmt: skip
    totals = usage_totals(row.record for row in rows if row.record is not None)
    dispatch = next(
        (a for s in state.completed_steps if (a := first_action(s, ActionType.DISPATCH))), None
    )
    metadata = action_metadata(dispatch)
    usage = next((row.record for row in rows if row.action_type == ActionType.DISPATCH), None)
    return totals.cost_usd, totals.turns, effort_sent_value(metadata, usage), prompt_identity(metadata)


def _result(
    outcome: ProducerOutcome, detail: str | None, state: RunState | None
) -> ProducerClassification:
    cost, turns, effort, prompt = (None, None, None, None) if state is None else _usage(state)
    return ProducerClassification(
        outcome=outcome,
        absence=_ABSENCE[outcome],
        failure_detail=detail,
        run_id=None if state is None else state.run_id,
        cost_usd=cost,
        turns=turns,
        effort_sent=effort,
        prompt=prompt,
    )


def classify_producer_run(
    process: ProcessResult,
    state: RunState | None,
    head_before: str,
    head_after: str,
    issue_sha256: str | None,
) -> ProducerClassification:
    """Map one finished producer run to its D10 outcome, absence class and detail.

    ``issue_sha256`` is the hash of the frozen issue file a fix run must have used; a run of a
    pipeline with no frozen text (a slice case's ``P6``, slice 426) passes ``None``.
    """
    if state is None or state.status == RUNNING_STATUS:
        what = "no readable run state" if state is None else "run state still 'running'"
        return _result(
            ProducerOutcome.NO_RUN_STATE,
            _detail(f"sq exited {process.returncode} with {what}", None, process),
            state,
        )
    if issue_sha256 is not None and (problem := _frozen_text_problem(state, issue_sha256)):
        return _result(ProducerOutcome.FROZEN_TEXT_MISMATCH, _detail(problem, None, process), state)
    kinds = _failed_kinds(state)
    if FailureKind.COST_CAP in kinds:
        return _result(
            ProducerOutcome.COST_CAP, _detail(FailureKind.COST_CAP.value, state, process), state
        )
    if awaits_human(state):
        return _result(
            ProducerOutcome.BLOCKED, _detail("paused awaiting a human", state, process), state
        )
    moved = head_after != head_before
    if state.status == ExecutionStatus.COMPLETED and moved:
        return _result(ProducerOutcome.COMMITTED, None, state)
    refused = state.status == ExecutionStatus.FAILED and FailureKind.FIX_REPORT in kinds
    if (state.status == ExecutionStatus.COMPLETED or refused) and not moved:
        label = FailureKind.FIX_REPORT.value if refused else "completed without a commit"
        return _result(ProducerOutcome.NO_COMMIT, _detail(label, state, process), state)
    label = ", ".join(kind.value for kind in kinds) or f"run status {state.status}"
    return _result(ProducerOutcome.PRODUCER_FAILED, _detail(label, state, process), state)


def spent_usd(state: RunState) -> float:
    """Known spend recorded in *state* across every invocation of the run."""
    cost, _, _, _ = _usage(state)
    return cost or 0.0
