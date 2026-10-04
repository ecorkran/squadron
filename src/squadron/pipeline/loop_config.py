"""Loop grammar — exit conditions, exhaust behavior, and parsed loop config.

Shared by the executor, the ``loop:`` step type's validation, and the
``cf.slices_needing_tasks`` source, which gates on the same thresholds (slice 195
D7). ``squadron.pipeline.executor`` re-exports these names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadron.pipeline.models import ActionResult
from squadron.review.models import Verdict


class LoopCondition(StrEnum):
    """Closed set of loop exit conditions."""

    REVIEW_PASS = "review.pass"
    REVIEW_CONCERNS_OR_BETTER = "review.concerns_or_better"
    ACTION_SUCCESS = "action.success"

    def met_by_verdict(self, verdict: str) -> bool:
        """Whether a review *verdict* meets this threshold — the single
        definition of the verdict sets (slice 195 D7).

        Raises ValueError for ``action.success``, which has no verdict meaning.
        """
        match self:
            case LoopCondition.REVIEW_PASS:
                return verdict == Verdict.PASS
            case LoopCondition.REVIEW_CONCERNS_OR_BETTER:
                return verdict in (Verdict.PASS, Verdict.CONCERNS)
            case LoopCondition.ACTION_SUCCESS:
                raise ValueError(f"{self.value} is not a review verdict threshold")

    @property
    def minimum_verdict(self) -> Verdict:
        """The lowest verdict that meets this threshold, for messages."""
        match self:
            case LoopCondition.REVIEW_PASS:
                return Verdict.PASS
            case LoopCondition.REVIEW_CONCERNS_OR_BETTER:
                return Verdict.CONCERNS
            case LoopCondition.ACTION_SUCCESS:
                raise ValueError(f"{self.value} is not a review verdict threshold")


def evaluate_condition(
    condition: LoopCondition,
    action_results: list[ActionResult],
) -> bool:
    """Return True if *condition* is satisfied by *action_results*.

    Returns False if no matching results are found (e.g. no review action).
    """
    if condition is LoopCondition.ACTION_SUCCESS:
        return bool(action_results) and all(r.success for r in action_results)
    last_review = last_with_verdict(action_results)
    return (
        last_review is not None
        and last_review.verdict is not None
        and condition.met_by_verdict(last_review.verdict)
    )


def last_with_verdict(results: list[ActionResult]) -> ActionResult | None:
    """The most recent verdict-bearing result in *results*, if any."""
    for result in reversed(results):
        if result.verdict is not None:
            return result
    return None


class ExhaustBehavior(StrEnum):
    """What to do when a loop reaches max iterations without the condition."""

    FAIL = "fail"
    CHECKPOINT = "checkpoint"
    SKIP = "skip"


@dataclass
class LoopConfig:
    """Parsed loop configuration from a step config dict."""

    max: int
    until: LoopCondition | None = None
    on_exhaust: ExhaustBehavior = ExhaustBehavior.FAIL
    strategy: str | None = None
    commit_each_iteration: bool = False
    # Second threshold, applied on exhaust (slice 195 D6).
    accept_if: LoopCondition | None = None
    # Skip every round when the verdict already in scope meets `until`.
    skip_if_met: bool = False


def parse_loop_config(loop_dict: dict[str, object]) -> LoopConfig:
    """Parse a raw loop dict into a LoopConfig.

    Raises ValueError for invalid ``max``, ``until``, ``accept_if`` or
    ``on_exhaust`` values, naming the field.
    """
    # A param-sourced max arrives as the placeholder's string (D6).
    max_raw = loop_dict.get("max")
    max_iter = int(max_raw) if isinstance(max_raw, str) and max_raw.isdecimal() else max_raw
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 1:
        raise ValueError(f"loop.max must be a positive integer, got: {max_raw!r}")

    on_exhaust_raw = loop_dict.get("on_exhaust", ExhaustBehavior.FAIL.value)
    try:
        on_exhaust = ExhaustBehavior(on_exhaust_raw)
    except ValueError:
        valid_ex = [b.value for b in ExhaustBehavior]
        raise ValueError(f"Invalid on_exhaust value {on_exhaust_raw!r}. Valid: {valid_ex}") from None

    strategy = loop_dict.get("strategy")

    return LoopConfig(
        max=max_iter,
        until=_parse_loop_condition(loop_dict, "until"),
        on_exhaust=on_exhaust,
        strategy=strategy if isinstance(strategy, str) else None,
        commit_each_iteration=loop_dict.get("commit_each_iteration") is True,
        accept_if=_parse_loop_condition(loop_dict, "accept_if"),
        skip_if_met=loop_dict.get("skip_if_met") is True,
    )


def _parse_loop_condition(loop_dict: dict[str, object], field: str) -> LoopCondition | None:
    raw = loop_dict.get(field)
    if raw is None:
        return None
    try:
        return LoopCondition(raw)
    except ValueError:
        valid = [c.value for c in LoopCondition]
        raise ValueError(f"Invalid loop.{field} value {raw!r}. Valid: {valid}") from None
