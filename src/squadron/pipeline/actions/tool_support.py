"""Shared runtime resolution of a step's ``allowed_tools`` parameter.

Load-time validation (``pipeline.steps.utils.validate_allowed_tools``) is the single
authority on whether a name is registered; this is its runtime counterpart, narrowing the
already-validated value out of ``ActionContext.params`` for the actions that pass it to a
provider. Dispatch, review, and summary all use this one implementation so the three cannot
drift apart in how they read the same field.
"""

from __future__ import annotations

from typing import cast

from squadron.pipeline.models import ActionContext


def resolve_allowed_tools(context: ActionContext, action_type: str) -> list[str] | None:
    """Narrow ``context.params["allowed_tools"]`` to a list of tool names.

    Names are not re-checked against the tool registry here: load-time validation is the
    single authority (design D3). A malformed value is a defect that validation should have
    caught, so it raises rather than silently dropping tools — a silent drop reproduces
    exactly the no-op-with-prose failure this slice exists to prevent.
    """
    raw = context.params.get("allowed_tools")
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(name, str) for name in raw):  # pyright: ignore[reportUnknownVariableType]
        raise ValueError(f"{action_type}: 'allowed_tools' must be a list of tool names, got {raw!r}")
    return cast(list[str], raw)
