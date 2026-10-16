"""Read a replay's outcome from the run state its ``sq run`` left (slice 177 D4).

Pure over ``RunState``: no file or git access. A replay run is P4 or P5, so its state is a
phase step (design or tasks), the revise loop that follows it, and a summary. Only the
phase step and the loop decide the outcome; a failing summary step does not un-produce an
accepted artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from pydantic import ValidationError

from squadron.metrology.replay_models import PromptIdentity, ReplayOutcome
from squadron.pipeline.actions import ActionType
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.state import RunState, StepState
from squadron.pipeline.steps import StepTypeName
from squadron.stats.producer_units import (
    PHASE_TYPES,
    loop_rounds,
    phase_accepted,
    unit_usage,
)
from squadron.stats.usage_report import action_usage_row, usage_totals


class FailureClass(StrEnum):
    """Why a replay run failed (D4); the record stores the value."""

    DISPATCH_ERROR = "dispatch_error"
    STALL = "stall"
    NO_ARTIFACT = "no_artifact"
    OTHER = "other"
    NO_RUN_STATE = "no_run_state"


_CLASS_OF_KIND: dict[FailureKind, FailureClass] = {
    FailureKind.PROVIDER_ERROR: FailureClass.DISPATCH_ERROR,
    FailureKind.STALL: FailureClass.STALL,
    FailureKind.ARTIFACT_MISSING: FailureClass.NO_ARTIFACT,
}


@dataclass(frozen=True)
class OutcomeReading:
    """What the run state says about one replayed config."""

    outcome: ReplayOutcome
    rounds: int | None  # the first review is round 1; each loop round adds one
    failure_class: FailureClass | None
    failure_detail: str | None
    first_verdict: str | None
    cost_usd: float | None
    priced: tuple[int, int]  # (records with a cost, LLM actions)
    prompt: PromptIdentity | None
    task_prompt: str | None  # the build_context stdout the producer was given
    effort_sent: str | None
    producer_model: str | None
    producer_profile: str | None


def no_run_state_reading(detail: str) -> OutcomeReading:
    """A run that left no run file: the subprocess exit code and stderr tail are the detail."""
    return OutcomeReading(
        outcome=ReplayOutcome.FAILED,
        rounds=None,
        failure_class=FailureClass.NO_RUN_STATE,
        failure_detail=detail,
        first_verdict=None,
        cost_usd=None,
        priced=(0, 0),
        prompt=None,
        task_prompt=None,
        effort_sent=None,
        producer_model=None,
        producer_profile=None,
    )


def read_outcome(state: RunState) -> OutcomeReading:
    """Map ``state`` to the D4 table. A state with no phase step is a failed run."""
    steps = state.completed_steps
    phase = next((step for step in steps if step.step_type in PHASE_TYPES), None)
    if phase is None:
        return _reading(
            state, None, None, ReplayOutcome.FAILED, None, *_failure_of(steps, "no phase step ran")
        )
    loop = _loop_after(steps, phase)
    outcome, rounds, failure = _decide(phase, loop)
    return _reading(state, phase, loop, outcome, rounds, *failure)


def _decide(
    phase: StepState, loop: StepState | None
) -> tuple[ReplayOutcome, int | None, tuple[FailureClass | None, str | None]]:
    none: tuple[FailureClass | None, str | None] = (None, None)
    if phase.status == ExecutionStatus.FAILED:
        return ReplayOutcome.FAILED, None, _failure_of([phase], "phase step failed")
    if phase.status != ExecutionStatus.COMPLETED:
        return ReplayOutcome.FAILED, None, (FailureClass.OTHER, f"phase step {phase.status}")
    rounds = 1 + loop_rounds(loop)
    if loop is not None and loop.exhausted and not loop.accepted:
        return ReplayOutcome.EXHAUSTED, rounds, none  # whatever on_exhaust did next
    if loop is not None and loop.status == ExecutionStatus.FAILED:
        return ReplayOutcome.FAILED, None, _failure_of([loop], "loop step failed")
    if phase_accepted(phase, loop):
        return ReplayOutcome.ACCEPTED, rounds, none
    status = "no loop step" if loop is None else f"loop step {loop.status}"
    return ReplayOutcome.FAILED, None, (FailureClass.OTHER, f"{status}; not accepted")


def _failure_of(steps: list[StepState], fallback: str) -> tuple[FailureClass | None, str | None]:
    """Classify the first failed action in ``steps`` by its stamped kind, else as ``other``."""
    for step in steps:
        for actions in (step.action_results, *reversed(step.prior_round_results)):
            for action in actions:
                if action.get("success") is not False:
                    continue
                kind = _kind(action)
                if kind is not None:
                    return _CLASS_OF_KIND[kind], _text(action.get("error"))
                return FailureClass.OTHER, _text(action.get("error")) or fallback
    return FailureClass.OTHER, fallback


def _kind(action: Mapping[str, object]) -> FailureKind | None:
    metadata = action.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    raw = cast("Mapping[str, object]", metadata).get(FAILURE_KIND_KEY)
    try:
        return None if raw is None else FailureKind(str(raw))
    except ValueError:
        return None  # a kind this reader does not know is `other`, with the error text


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _loop_after(steps: list[StepState], phase: StepState) -> StepState | None:
    """The loop directly after the phase step; a resumed run's last record of it wins."""
    position = steps.index(phase)
    if position + 1 >= len(steps) or steps[position + 1].step_type != StepTypeName.LOOP:
        return None
    name = steps[position + 1].step_name
    return next(step for step in reversed(steps[position + 1 :]) if step.step_name == name)


def _reading(
    state: RunState,
    phase: StepState | None,
    loop: StepState | None,
    outcome: ReplayOutcome,
    rounds: int | None,
    failure_class: FailureClass | None,
    failure_detail: str | None,
) -> OutcomeReading:
    dispatch = _first_action(phase, ActionType.DISPATCH)
    usage = (
        None
        if dispatch is None or phase is None
        else action_usage_row(state.run_id, phase.step_name, dispatch).record
    )
    spent = None if phase is None else unit_usage(state.run_id, phase, loop)
    totals = None if spent is None else usage_totals(spent.records)
    metadata = _metadata(dispatch)
    return OutcomeReading(
        outcome=outcome,
        rounds=rounds,
        failure_class=failure_class,
        failure_detail=failure_detail,
        first_verdict=None if phase is None else phase.verdict,
        cost_usd=None if totals is None else totals.cost_usd,
        priced=(0, 0) if spent is None or totals is None else (totals.priced, spent.llm_actions),
        prompt=_prompt_identity(metadata),
        task_prompt=_build_context_text(phase),
        effort_sent=None if usage is None else usage.effort,
        producer_model=_text(metadata.get("model")) or _text(metadata.get("requested_model")),
        producer_profile=_text(metadata.get("profile")),
    )


def _first_action(step: StepState | None, action_type: ActionType) -> Mapping[str, object] | None:
    if step is None:
        return None
    return next((a for a in step.action_results if a.get("action_type") == action_type), None)


def _metadata(action: Mapping[str, object] | None) -> Mapping[str, object]:
    raw = None if action is None else action.get("metadata")
    return cast("Mapping[str, object]", raw) if isinstance(raw, Mapping) else {}


def _prompt_identity(metadata: Mapping[str, object]) -> PromptIdentity | None:
    raw = metadata.get("prompt")
    if not isinstance(raw, Mapping):
        return None
    try:
        return PromptIdentity.model_validate(raw)
    except ValidationError:
        return None  # a prompt identity this version cannot read is recorded as absent


def _build_context_text(phase: StepState | None) -> str | None:
    """The ``build_context`` stdout the phase step's dispatch was given."""
    if phase is None:
        return None
    for action in phase.action_results:
        outputs = action.get("outputs")
        if (
            action.get("action_type") == ActionType.CF_OP
            and isinstance(outputs, Mapping)
            and cast("Mapping[str, object]", outputs).get("operation") == "build_context"
        ):
            return _text(cast("Mapping[str, object]", outputs).get("stdout"))
    return None
