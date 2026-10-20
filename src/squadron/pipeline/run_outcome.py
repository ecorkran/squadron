"""Machine-readable run outcome for ``sq runs wait --json`` (#244, Amoeba S10).

The run-state file is internal; this is the stable shape an external caller reads
instead. Keys are documented in docs/COMMANDS.md. A key that does not apply, or
that cannot be determined, is ``None``: a reader treats it as unknown and never
substitutes a default. No prompt text is emitted.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum

import yaml
from pydantic import ValidationError

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.executor import ExecutionStatus, resolve_placeholders
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.run_wait import WaitOutcome
from squadron.pipeline.state import RunState, StepState
from squadron.pipeline.steps import StepTypeName

_logger = logging.getLogger(__name__)

DefinitionLoader = Callable[[str], PipelineDefinition]


class CheckpointKind(StrEnum):
    """Why a run paused; each routes differently for a caller."""

    LOOP_EXHAUSTED = "loop_exhausted"  # a loop ran out of rounds (on_exhaust: checkpoint)
    INTERACTIVE_CHECKPOINT = "interactive_checkpoint"  # a checkpoint: prompt took exit
    AWAITS_HUMAN = "awaits_human"  # an action handed off to a person (e.g. a BLOCKED task)
    OTHER = "other"


def run_outcome(
    run_id: str,
    outcome: WaitOutcome,
    state: RunState | None,
    load_definition: DefinitionLoader = load_pipeline,
) -> dict[str, object]:
    """The outcome document for *run_id*; *state* is ``None`` when it could not be read."""
    doc: dict[str, object] = {"run_id": run_id, "outcome": outcome.value}
    if state is None:
        return doc
    doc |= {
        "status": state.status,
        "pipeline": state.pipeline,
        "started_at": state.started_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
        "checkpoint": None,
        "failure": None,
        "reviews": _reviews(state),
    }
    if state.status == ExecutionStatus.PAUSED.value:
        doc["checkpoint"] = _checkpoint(state, load_definition)
    elif state.status == ExecutionStatus.FAILED.value:
        doc["failure"] = _failure(state)
    return doc


def _reviews(state: RunState) -> list[dict[str, object]]:
    """Every review the run recorded, in the order written (#244 follow-up, Amoeba S13).

    A loop step's earlier rounds come before its final round; a resumed step
    contributes again as its own recorded step.
    """
    found: list[dict[str, object]] = []
    for step in state.completed_steps:
        rounds = [*step.prior_round_results, step.action_results]
        first_round = step.iteration - len(rounds) + 1
        for offset, actions in enumerate(rounds):
            round_number = first_round + offset if step.step_type == StepTypeName.LOOP else None
            found += [_review_entry(step, a, round_number) for a in actions if _is_review(a)]
    return found


def _is_review(action: dict[str, object]) -> bool:
    return action.get("action_type") == ActionType.REVIEW


def _review_entry(
    step: StepState, action: dict[str, object], round_number: int | None
) -> dict[str, object]:
    outputs = _outputs(action)
    path = outputs.get(ReviewOutputKey.REVIEW_FILE)
    parts = outputs.get(ReviewOutputKey.REVIEW_FILES)
    metadata = action.get("metadata")
    template = metadata.get("template") if isinstance(metadata, dict) else None  # type: ignore[union-attr]
    verdict = action.get("verdict")
    return {
        "path": path if isinstance(path, str) and path else None,
        "paths": [p for p in parts if isinstance(p, str)] if isinstance(parts, list) else None,  # type: ignore[union-attr]
        "template": template if isinstance(template, str) else None,
        "verdict": verdict if isinstance(verdict, str) else None,
        "step": step.step_name,
        "round": round_number,
    }


def _last_step(state: RunState, name: str | None, status: str) -> StepState | None:
    for step in reversed(state.completed_steps):
        if step.status == status and (name is None or step.step_name == name):
            return step
    return None


def _checkpoint(state: RunState, load_definition: DefinitionLoader) -> dict[str, object]:
    recorded = state.checkpoint
    step = _last_step(state, recorded.step if recorded else None, ExecutionStatus.PAUSED.value)
    is_loop = step is not None and step.step_type == StepTypeName.LOOP
    return {
        "kind": _checkpoint_kind(step).value if step is not None else None,
        "step": step.step_name if step is not None else (recorded.step if recorded else None),
        "step_type": step.step_type if step is not None else None,
        "is_loop": is_loop if step is not None else None,
        "round": step.iteration if is_loop and step is not None else None,
        "max_rounds": _max_rounds(state, step.step_name, load_definition)
        if is_loop and step is not None
        else None,
        "verdict": recorded.verdict if recorded else None,
        "review_file": _review_file(step) if step is not None else None,
        "reason": recorded.reason if recorded else None,
        "paused_at": recorded.paused_at.isoformat() if recorded else None,
    }


def _checkpoint_kind(step: StepState) -> CheckpointKind:
    actions = step.action_results
    if any(a.get("awaits_human") is True for a in actions):
        return CheckpointKind.AWAITS_HUMAN
    if any(_outputs(a).get("checkpoint") == "paused" for a in actions):
        return CheckpointKind.INTERACTIVE_CHECKPOINT
    if step.exhausted:
        return CheckpointKind.LOOP_EXHAUSTED
    return CheckpointKind.OTHER


def _outputs(action: dict[str, object]) -> dict[str, object]:
    outputs = action.get("outputs")
    return outputs if isinstance(outputs, dict) else {}  # type: ignore[return-value]


def _review_file(step: StepState) -> str | None:
    """The review artifact behind the step's last verdict."""
    for action in reversed(step.action_results):
        path = _outputs(action).get(ReviewOutputKey.REVIEW_FILE)
        if isinstance(path, str) and path:
            return path
    return None


def _max_rounds(state: RunState, step_name: str, load_definition: DefinitionLoader) -> int | None:
    """The loop's configured ``max``, resolved against the run's params; ``None`` if unknown."""
    try:
        definition = load_definition(state.load_target)
    except (FileNotFoundError, ValidationError, yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        # The outcome is still reportable; the round limit is reported as unknown.
        _logger.warning(
            "run %s: cannot reload %s for max_rounds: %s", state.run_id, state.load_target, exc
        )
        return None
    step = next((s for s in definition.steps if s.name == step_name), None)
    if step is None:
        return None
    params = {**definition.params, **state.params}
    raw = resolve_placeholders({"max": step.config.get("max")}, params)["max"]
    try:
        return int(str(raw))
    except ValueError:
        return None


def _failure(state: RunState) -> dict[str, object]:
    step = _last_step(state, None, ExecutionStatus.FAILED.value)
    failed = (
        next((a for a in reversed(step.action_results) if a.get("success") is False), None)
        if step is not None
        else None
    )
    metadata = failed.get("metadata") if failed is not None else None
    kind = metadata.get(FAILURE_KIND_KEY) if isinstance(metadata, dict) else None  # type: ignore[union-attr]
    message = failed.get("error") if failed is not None else None
    return {
        "kind": kind if isinstance(kind, str) else None,
        "step": step.step_name if step is not None else None,
        "message": message if isinstance(message, str) else None,
    }
