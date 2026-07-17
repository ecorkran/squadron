"""Gate action — reduces a judge verdict and a review verdict to one verdict."""

from __future__ import annotations

import logging
from enum import IntEnum

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.actions.judge import Provenance
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_GATE_POLICY = "most-severe"
VALID_GATE_POLICIES = {DEFAULT_GATE_POLICY}


class _Severity(IntEnum):
    """Verdict severity ranking, most severe first (highest value = most severe).

    UNKNOWN is ranked most severe deliberately: a judgment that could not be
    rendered must dominate a passing leg, never be masked by it (no-silent-pass).
    """

    PASS = 0
    CONCERNS = 1
    FAIL = 2
    UNKNOWN = 3


def _normalize(verdict: str | None) -> str:
    """Map a None verdict to UNKNOWN before ranking (fail-closed, F001)."""
    return verdict if verdict is not None else "UNKNOWN"


def reduce_verdicts(a: str | None, b: str | None) -> str:
    """Reduce two verdicts to the more severe of the pair (most-severe-wins).

    None is normalized to UNKNOWN before ranking, so a verdict-less leg
    dominates rather than vanishing. Pure function: no I/O, no logging —
    callers that need to observe a None leg (e.g. GateAction) log it
    themselves before calling this.
    """
    severity_a = _Severity[_normalize(a)]
    severity_b = _Severity[_normalize(b)]
    return max(severity_a, severity_b).name


class GateAction:
    """Pipeline action that reduces a judge result and a review result to one verdict.

    Resolves two named prior steps via ``context.step_outputs``, reduces their
    verdicts by most-severe-wins, and returns a single ``ActionResult`` with
    ``composed`` provenance. Both raw verdicts are preserved on ``metadata``
    for auditability. Does not modify the checkpoint or its read path.
    """

    @property
    def action_type(self) -> str:
        return ActionType.GATE

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if "judge_from" not in config:
            errors.append(
                ValidationError(
                    field="judge_from",
                    message="'judge_from' is required",
                    action_type=self.action_type,
                )
            )
        if "review_from" not in config:
            errors.append(
                ValidationError(
                    field="review_from",
                    message="'review_from' is required",
                    action_type=self.action_type,
                )
            )
        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        judge_from = str(context.params.get("judge_from", ""))
        review_from = str(context.params.get("review_from", ""))
        policy = str(context.params.get("policy", DEFAULT_GATE_POLICY))

        if policy not in VALID_GATE_POLICIES:
            _logger.warning(
                "gate: unknown policy '%s'; falling back to '%s'",
                policy,
                DEFAULT_GATE_POLICY,
            )
            policy = DEFAULT_GATE_POLICY

        judge_result = context.step_outputs.get(judge_from)
        review_result = context.step_outputs.get(review_from)

        if judge_result is None:
            _logger.warning(
                "gate: judge_from step '%s' not found in step_outputs; verdict=UNKNOWN",
                judge_from,
            )
        if review_result is None:
            _logger.warning(
                "gate: review_from step '%s' not found in step_outputs; verdict=UNKNOWN",
                review_from,
            )

        judge_verdict = judge_result.verdict if judge_result is not None else None
        review_verdict = review_result.verdict if review_result is not None else None

        if judge_result is not None and judge_verdict is None:
            _logger.warning(
                "gate: judge_from step '%s' produced no verdict; normalizing to UNKNOWN",
                judge_from,
            )
        if review_result is not None and review_verdict is None:
            _logger.warning(
                "gate: review_from step '%s' produced no verdict; normalizing to UNKNOWN",
                review_from,
            )

        # Only one policy exists today (most-severe-wins, applied by
        # reduce_verdicts unconditionally) — policy is validated and recorded
        # for auditability rather than dispatched on, per the project rule
        # against building a single-entry registry ahead of a second caller.
        reduced = reduce_verdicts(judge_verdict, review_verdict)

        # success=True regardless of the reduced verdict: it reports that the
        # gate action itself executed and produced a verdict, not that the
        # verdict passed — mirroring CheckpointAction, whose fired/skipped
        # results are both success=True. The checkpoint step (if configured)
        # is what acts on a non-passing `verdict`.
        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={
                "judge_from": judge_from,
                "review_from": review_from,
            },
            verdict=reduced,
            provenance=Provenance.COMPOSED,
            metadata={
                "policy": policy,
                "judge_verdict": _normalize(judge_verdict),
                "review_verdict": _normalize(review_verdict),
                "judge_score": judge_result.score if judge_result is not None else None,
                "review_score": review_result.score if review_result is not None else None,
                "judge_criteria": judge_result.criteria if judge_result is not None else None,
                "review_criteria": review_result.criteria if review_result is not None else None,
            },
        )


register_action(ActionType.GATE, GateAction())
