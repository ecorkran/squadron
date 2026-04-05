"""Checkpoint action — quality gate that evaluates prior review verdicts."""

from __future__ import annotations

from enum import StrEnum

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


class CheckpointTrigger(StrEnum):
    """When a checkpoint should fire based on the prior review verdict."""

    ALWAYS = "always"
    ON_CONCERNS = "on-concerns"
    ON_FAIL = "on-fail"
    NEVER = "never"


_TRIGGER_THRESHOLDS: dict[CheckpointTrigger, set[str]] = {
    CheckpointTrigger.ALWAYS: set(),  # fires regardless
    CheckpointTrigger.ON_CONCERNS: {"CONCERNS", "FAIL"},
    CheckpointTrigger.ON_FAIL: {"FAIL"},
    CheckpointTrigger.NEVER: set(),  # never fires
}


def _find_review_verdict(prior_outputs: dict[str, ActionResult]) -> str | None:
    """Find the most recent review verdict from prior action outputs.

    Iterates prior_outputs in reverse insertion order and returns the
    first ``result.verdict`` that is not ``None``.
    """
    for result in reversed(list(prior_outputs.values())):
        if result.verdict is not None:
            return result.verdict
    return None


def _should_fire(trigger: CheckpointTrigger, verdict: str | None) -> bool:
    """Evaluate whether the checkpoint should fire given a trigger and verdict."""
    if trigger == CheckpointTrigger.ALWAYS:
        return True
    if trigger == CheckpointTrigger.NEVER:
        return False
    if verdict is None:
        return False
    return verdict in _TRIGGER_THRESHOLDS[trigger]


class CheckpointAction:
    """Pipeline action that gates execution based on prior review verdicts.

    Evaluates a trigger condition against the most recent review verdict
    from ``context.prior_outputs``. Returns data indicating whether the
    pipeline should pause — the executor (slice 149) interprets the result.
    """

    @property
    def action_type(self) -> str:
        return ActionType.CHECKPOINT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        trigger_val = config.get("trigger")
        if trigger_val is not None:
            try:
                CheckpointTrigger(str(trigger_val))
            except ValueError:
                valid = [t.value for t in CheckpointTrigger]
                return [
                    ValidationError(
                        field="trigger",
                        message=(
                            f"Invalid trigger value '{trigger_val}'. "
                            f"Valid values: {valid}"
                        ),
                        action_type=ActionType.CHECKPOINT,
                    )
                ]
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        # Trigger resolution
        trigger_str = str(context.params.get("trigger", CheckpointTrigger.ON_CONCERNS))
        try:
            trigger = CheckpointTrigger(trigger_str)
        except ValueError:
            valid = [t.value for t in CheckpointTrigger]
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={
                    "error": (
                        f"Invalid checkpoint trigger '{trigger_str}'. "
                        f"Valid values: {valid}"
                    ),
                },
            )

        # Prior verdict lookup
        verdict = _find_review_verdict(context.prior_outputs)

        # Trigger evaluation
        if _should_fire(trigger, verdict):
            return ActionResult(
                success=True,
                action_type=self.action_type,
                outputs={
                    "checkpoint": "paused",
                    "reason": f"Review verdict: {verdict}",
                    "trigger": trigger.value,
                    "human_options": ["approve", "revise", "skip", "abort"],
                },
                verdict=verdict,
                metadata={
                    "step": context.step_name,
                    "pipeline": context.pipeline_name,
                },
            )

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={
                "checkpoint": "skipped",
                "trigger": trigger.value,
                "verdict_seen": verdict or "none",
            },
        )


register_action(ActionType.CHECKPOINT, CheckpointAction())
