"""The findings-addressed gate policy — sequences the layers and derives the verdict.

Layer order is the whole point: screens (free) before judge (paid), and a
verdict computed from statuses rather than taken from the model.
"""

from __future__ import annotations

import logging

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.findings_addressed.judge import JudgeLegResult, judge_residue
from squadron.pipeline.actions.findings_addressed.models import (
    FindingOutcome,
    FindingRecord,
    SettlingScreen,
    concern_plus,
    read_findings,
)
from squadron.pipeline.actions.findings_addressed.screens import (
    RoundDiff,
    ScreenResult,
    compute_round_diff,
    run_deterministic_screens,
    screen_no_prior_round,
)
from squadron.pipeline.actions.findings_addressed.verification import (
    derive_addressed_verdict,
    verify_outcomes,
)
from squadron.pipeline.actions.judge import Provenance
from squadron.pipeline.models import ActionContext, ActionResult

_logger = logging.getLogger(__name__)

#: An empty RoundDiff for the paths that never measure one (no prior round).
_NO_DIFF = RoundDiff(changed_paths=frozenset(), is_empty=False, prior_sha=None)


class FindingsAddressedPolicy:
    """Decide whether the round addressed the prior round's CONCERN+ findings."""

    async def evaluate(self, context: ActionContext) -> ActionResult:
        from squadron.pipeline.actions.gate import GatePolicy, reduce_verdicts

        review_from = str(context.params.get("review_from", ""))
        fresh_result = context.step_outputs.get(review_from)
        if fresh_result is None:
            _logger.warning(
                "findings-addressed: review_from step '%s' not found in step_outputs; verdict=UNKNOWN",
                review_from,
            )
        fresh_verdict = fresh_result.verdict if fresh_result is not None else None
        fresh_findings = read_findings(fresh_result)

        screen, diff = self._run_screens(context, review_from, fresh_findings)

        outcomes = list(screen.outcomes)
        judge = JudgeLegResult()
        if screen.leg_verdict is not None:
            addressed_verdict = screen.leg_verdict
        else:
            judge = await judge_residue(
                context,
                residue=screen.residue,
                fresh_findings=fresh_findings,
                diff=diff,
            )
            outcomes.extend(
                verify_outcomes(
                    judge.outcomes,
                    residue=screen.residue,
                    fresh_findings=fresh_findings,
                    diff=diff,
                )
            )
            addressed_verdict = derive_addressed_verdict(outcomes, judge_failed=judge.failed)

        reduced = reduce_verdicts(addressed_verdict, fresh_verdict)
        _logger.info(
            "findings-addressed: addressed=%s review=%s -> %s (%d finding outcome(s))",
            addressed_verdict,
            fresh_verdict,
            reduced,
            len(outcomes),
        )

        return ActionResult(
            success=True,
            action_type=ActionType.GATE,
            outputs={"review_from": review_from},
            verdict=reduced,
            provenance=Provenance.COMPOSED,
            metadata={
                "policy": GatePolicy.FINDINGS_ADDRESSED.value,
                "addressed_verdict": addressed_verdict,
                "review_verdict": fresh_verdict,
                "no_prior_round": screen.deciding_screen == SettlingScreen.NO_PRIOR_ROUND,
                "deciding_screen": (
                    screen.deciding_screen.value if screen.deciding_screen is not None else None
                ),
                "finding_statuses": [_outcome_record(outcome) for outcome in outcomes],
                # The prior round's commit — HEAD at gate time. Round N's own
                # SHA is not recordable here (see RoundDiff.prior_sha).
                "prior_round_sha": diff.prior_sha,
                "revision_number": context.iteration if context.iteration >= 1 else None,
                "judge_model": judge.model,
                "judge_template": judge.template,
            },
        )

    def _run_screens(
        self,
        context: ActionContext,
        review_from: str,
        fresh_findings: list[FindingRecord],
    ) -> tuple[ScreenResult, RoundDiff]:
        """Screen 0 first — it is decided before any git call, having nothing to measure."""
        prior_result = context.prior_iteration_step_outputs.get(review_from)
        if prior_result is None:
            return (
                screen_no_prior_round(
                    pipeline_name=context.pipeline_name,
                    step_name=context.step_name,
                    iteration=context.iteration,
                ),
                _NO_DIFF,
            )

        # Measured over the whole tree: scoping to the loop's artifact paths is
        # supported by compute_round_diff but has no config surface yet, and a
        # silently-ignored `paths:` would be worse than none.
        diff = compute_round_diff(cwd=context.cwd)
        prior_findings = concern_plus(read_findings(prior_result))
        return (
            run_deterministic_screens(
                prior_findings=prior_findings,
                fresh_findings=fresh_findings,
                diff=diff,
            ),
            diff,
        )


def register() -> None:
    """Register this policy with the gate action's registry.

    Called from ``actions/gate.py`` at import time rather than executed here at
    module scope: the gate action is the registry's owner, and importing it is
    what must guarantee its policies exist.
    """
    from squadron.pipeline.actions.gate import GatePolicy, register_gate_policy

    register_gate_policy(GatePolicy.FINDINGS_ADDRESSED, FindingsAddressedPolicy())


def _outcome_record(outcome: FindingOutcome) -> dict[str, object]:
    """One finding outcome as plain data for metadata and the evidence artifact."""
    return {
        "id": outcome.finding_id,
        "status": outcome.status.value,
        "screen": outcome.screen.value,
        "successor": outcome.successor_id,
        "note": outcome.note,
    }
