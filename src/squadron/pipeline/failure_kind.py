"""Why an action failed, as a value rather than error text (slice 177 D4).

Stamped in ``ActionResult.metadata`` where the failure is decided, so a reader of run
state (the replay outcome reader) classifies failures without matching error messages.
An action that fails for any other reason carries no kind.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from squadron.providers.sdk.rate_limit import UsageLimitReached

#: ``ActionResult.metadata`` key holding a ``FailureKind`` value.
FAILURE_KIND_KEY = "failure_kind"
#: ``ActionResult.metadata`` key holding a used-up usage limit's reset time (Unix s, #248).
USAGE_LIMIT_RESETS_AT_KEY = "usage_limit_resets_at"
#: ``ActionResult.metadata`` key holding what an agent asked when it ended on a question (#249).
AGENT_QUESTION_KEY = "agent_question"
#: ``ActionResult.metadata`` key holding the agent's final text when a dispatch wrote no artifact.
AGENT_TEXT_KEY = "agent_text"


class FailureKind(StrEnum):
    PROVIDER_ERROR = "provider_error"  # a dispatch's provider raised
    STALL = "stall"  # a dispatch produced no output within the stall bound (slice 174)
    ARTIFACT_MISSING = "artifact_missing"  # a phase dispatch wrote no artifact (slice 909/945)
    COST_CAP = "cost_cap"  # the run's known spend crossed pipeline.max_cost_usd (slice 947)
    USAGE_LIMIT = "usage_limit"  # the account's usage limit is used up; the run pauses (#248)
    AGENT_QUESTION = "agent_question"  # the agent ended on a question, no artifact; pauses (#249)


#: Kinds that wait on something outside the run (a reset, an answer); the rest fail it.
_PAUSING_KINDS = frozenset({FailureKind.USAGE_LIMIT.value, FailureKind.AGENT_QUESTION.value})


def pauses_run(metadata: Mapping[str, object]) -> bool:
    """Whether a failed action's kind pauses the run at its step rather than failing it.

    Waiting is the only fix for a used-up usage limit, and an agent's question needs an
    answer, so the step reruns on resume.
    """
    return metadata.get(FAILURE_KIND_KEY) in _PAUSING_KINDS


def usage_limit_stamp(exc: BaseException) -> dict[str, object]:
    """The metadata a used-up usage limit stamps on its action; empty for any other error."""
    if not isinstance(exc, UsageLimitReached):
        return {}
    return {
        FAILURE_KIND_KEY: FailureKind.USAGE_LIMIT.value,
        USAGE_LIMIT_RESETS_AT_KEY: exc.resets_at,
    }
