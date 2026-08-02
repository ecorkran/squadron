"""Gate action — reduces a judge verdict and a review verdict to one verdict."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Protocol

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.actions.judge import Provenance
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_logger = logging.getLogger(__name__)


class GatePolicy(StrEnum):
    """How a gate decides its verdict.

    ``MOST_SEVERE`` reduces two verdict-bearing legs (slice 304).
    ``FINDINGS_ADDRESSED`` additionally requires the prior round's CONCERN+
    findings to be accounted for (slice 305).
    """

    MOST_SEVERE = "most-severe"
    FINDINGS_ADDRESSED = "findings-addressed"


DEFAULT_GATE_POLICY: str = GatePolicy.MOST_SEVERE.value
VALID_GATE_POLICIES: frozenset[str] = frozenset(policy.value for policy in GatePolicy)


@dataclass(frozen=True)
class GatePolicyContract:
    """What a gate policy accepts in config.

    Single source of truth for the per-policy config surface, consumed by
    ``steps/gate.py`` (own-config validation and expansion), ``loader.py``
    (cross-step resolution), and ``steps/loop.py`` (unconsumed-verdict
    counting). None of those may restate the field names.
    """

    required: tuple[str, ...]
    forbidden: tuple[str, ...]
    # Whether the policy has a model layer configurable via a `judge:` block.
    supports_judge_block: bool


GATE_POLICY_CONTRACTS: dict[GatePolicy, GatePolicyContract] = {
    GatePolicy.MOST_SEVERE: GatePolicyContract(
        required=("judge_from", "review_from"),
        forbidden=(),
        supports_judge_block=False,
    ),
    # findings-addressed has no second verdict leg: the model layer it runs is
    # internal to the policy, not a separately-named judge step.
    GatePolicy.FINDINGS_ADDRESSED: GatePolicyContract(
        required=("review_from",),
        forbidden=("judge_from",),
        supports_judge_block=True,
    ),
}

# Keys accepted inside a gate step's optional `judge:` block.
JUDGE_BLOCK_KEYS: frozenset[str] = frozenset({"model"})


def policy_contract(policy: object) -> GatePolicyContract | None:
    """Return the config contract for *policy*.

    ``None`` (the field is absent from config) resolves to the default
    policy's contract. An unrecognized or non-string value returns ``None`` —
    the caller reports that as an invalid-policy error and skips field checks
    rather than reporting a second, misleading error against the wrong
    contract.
    """
    if policy is None:
        return GATE_POLICY_CONTRACTS[GatePolicy(DEFAULT_GATE_POLICY)]
    if not isinstance(policy, str):
        return None
    try:
        return GATE_POLICY_CONTRACTS[GatePolicy(policy)]
    except ValueError:
        return None


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


class GatePolicyImplementation(Protocol):
    """A gate policy's decision procedure.

    One implementation per ``GatePolicy`` member. Each returns the gate's
    ``ActionResult`` in full, including its own ``metadata["policy"]`` — the
    policy owns the shape of the evidence it records.
    """

    async def evaluate(self, context: ActionContext) -> ActionResult: ...


_POLICY_REGISTRY: dict[str, GatePolicyImplementation] = {}


def register_gate_policy(policy: GatePolicy, implementation: GatePolicyImplementation) -> None:
    """Register the implementation for *policy*.

    Each policy module registers itself on import, mirroring
    ``register_action`` at the foot of every action module.
    """
    _POLICY_REGISTRY[policy.value] = implementation


class MostSevereGatePolicy:
    """Reduce a judge leg and a review leg to the more severe of the two.

    Slice 304's original ``GateAction.execute`` body, unchanged.
    """

    async def evaluate(self, context: ActionContext) -> ActionResult:
        judge_from = str(context.params.get("judge_from", ""))
        review_from = str(context.params.get("review_from", ""))

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

        reduced = reduce_verdicts(judge_verdict, review_verdict)

        # success=True regardless of the reduced verdict: it reports that the
        # gate action itself executed and produced a verdict, not that the
        # verdict passed — mirroring CheckpointAction, whose fired/skipped
        # results are both success=True. The checkpoint step (if configured)
        # is what acts on a non-passing `verdict`.
        return ActionResult(
            success=True,
            action_type=ActionType.GATE,
            outputs={
                "judge_from": judge_from,
                "review_from": review_from,
            },
            verdict=reduced,
            provenance=Provenance.COMPOSED,
            metadata={
                "policy": GatePolicy.MOST_SEVERE.value,
                "judge_verdict": _normalize(judge_verdict),
                "review_verdict": _normalize(review_verdict),
                "judge_score": judge_result.score if judge_result is not None else None,
                "review_score": review_result.score if review_result is not None else None,
                "judge_criteria": judge_result.criteria if judge_result is not None else None,
                "review_criteria": review_result.criteria if review_result is not None else None,
            },
        )


class GateAction:
    """Pipeline action that resolves a gate's verdict under its configured policy.

    Owns policy resolution and dispatch only; the decision procedure itself
    lives in the registered ``GatePolicyImplementation``. Does not modify the
    checkpoint or its read path.
    """

    @property
    def action_type(self) -> str:
        return ActionType.GATE

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []
        contract = policy_contract(config.get("policy"))
        if contract is None:
            # Unrecognized policy — GateStepType.validate reports it; checking
            # reference fields against a contract we cannot identify would only
            # add a misleading second error.
            return errors
        for field_name in contract.required:
            if field_name not in config:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"'{field_name}' is required",
                        action_type=self.action_type,
                    )
                )
        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        policy = str(context.params.get("policy", DEFAULT_GATE_POLICY))

        if policy not in VALID_GATE_POLICIES:
            _logger.warning(
                "gate: unknown policy '%s'; falling back to '%s'",
                policy,
                DEFAULT_GATE_POLICY,
            )
            policy = DEFAULT_GATE_POLICY

        implementation = _POLICY_REGISTRY.get(policy)
        if implementation is None:
            # A valid policy whose module was never imported: the decision
            # could not be made at all. Fail closed and loudly rather than
            # silently substituting another policy's answer.
            message = (
                f"gate: policy '{policy}' has no registered implementation "
                f"(registered: {sorted(_POLICY_REGISTRY)})"
            )
            _logger.error(message)
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=message,
                verdict=_Severity.UNKNOWN.name,
                provenance=Provenance.COMPOSED,
                metadata={"policy": policy},
            )

        return await implementation.evaluate(context)


register_gate_policy(GatePolicy.MOST_SEVERE, MostSevereGatePolicy())
register_action(ActionType.GATE, GateAction())
