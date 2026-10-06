"""Param keys the executor sets itself, never a pipeline or ``-p`` (slice 197 D8, D9).

Defined once here. They are rejected wherever params enter a run, so a value under
one of these keys always came from a checkpoint resolution or an item-resume decision.
"""

from __future__ import annotations

# Instructions prepended to every dispatch prompt in scope (checkpoint resolution,
# ``sq run --resume … --instructions``).
OVERRIDE_INSTRUCTIONS = "override_instructions"
# Set by ``--decision accept``: the item's revise loop counts as met with no rounds.
ACCEPT_DECISION = "accept_decision"

# Each reserved key and the CLI flag that sets it, for the rejection message.
RESERVED_PARAMS: dict[str, str] = {
    OVERRIDE_INSTRUCTIONS: "--instructions",
    ACCEPT_DECISION: "--decision accept",
}


def reserved_param_error(key: str) -> str | None:
    """The rejection message for a reserved *key*; ``None`` when it is not reserved."""
    flag = RESERVED_PARAMS.get(key)
    return None if flag is None else f"'{key}' is reserved; use {flag}"
