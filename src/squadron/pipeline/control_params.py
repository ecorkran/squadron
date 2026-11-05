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
# Set on the step ``sq run --resume`` restarts when it paused for a person (an action
# returned ``awaits_human``). That step did not finish, so an ``existing: keep``
# implement step must dispatch again even though its branch already has commits.
RESUMED_FROM_HANDOFF = "resumed_from_handoff"
# Set by ``sq run --max-cost`` (#241). Kept in the run's params so a resume keeps the
# cap; a resume's own ``--max-cost`` replaces it.
RUN_MAX_COST = "run_max_cost_usd"
# Set by ``sq run --io-dir`` (#292): the absolute directory dispatch steps read
# ``prompt_files`` from and write ``reply_file``/``delivered_prompt_file`` to.
RUN_IO_DIR = "run_io_dir"
# Set by the executor at the start of each invocation (fresh run or resume): the HEAD a
# guarded ``commit`` step requires to be unchanged (#292).
RUN_START_HEAD = "run_start_head"

# Each reserved key and the CLI flag that sets it, for the rejection message.
RESERVED_PARAMS: dict[str, str] = {
    OVERRIDE_INSTRUCTIONS: "--instructions",
    ACCEPT_DECISION: "--decision accept",
    RESUMED_FROM_HANDOFF: "sq run --resume (it is set automatically for a hand-off pause)",
    RUN_MAX_COST: "--max-cost",
    RUN_IO_DIR: "--io-dir",
    RUN_START_HEAD: "nothing (sq run records it when the run starts)",
}


def reserved_param_error(key: str) -> str | None:
    """The rejection message for a reserved *key*; ``None`` when it is not reserved."""
    flag = RESERVED_PARAMS.get(key)
    return None if flag is None else f"'{key}' is reserved; use {flag}"
