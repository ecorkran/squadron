"""Shared runtime resolution of a step's ``allowed_tools`` parameter.

Load-time validation (``pipeline.steps.utils.validate_allowed_tools``) is the single
authority on whether a name is registered; this is its runtime counterpart, narrowing the
already-validated value out of ``ActionContext.params`` for the actions that pass it to a
provider. Dispatch, review, and summary all use this one implementation so the three cannot
drift apart in how they read the same field.
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import ActionContext
from squadron.providers.base import ProviderCapabilities


class DispatchRoute(StrEnum):
    """Which path a dispatch step takes to its model."""

    SESSION = "session"  # a persistent SDK session, whose tool set is fixed at connect time
    AGENT = "agent"  # a one-shot agent from the provider registry


def declares_no_tools(context: ActionContext) -> bool:
    """Whether the step set ``allowed_tools`` to an empty list (slice 949 D6).

    An absent key is not a declaration: it keeps each path's existing behavior.
    """
    return resolve_allowed_tools(context, ActionType.DISPATCH) == []


def tool_isolation_error(
    *,
    step_name: str,
    model: str,
    provider: str,
    route: DispatchRoute,
    capabilities: ProviderCapabilities,
) -> str | None:
    """The error for a no-tools step whose route would still run tools, else ``None``.

    A persistent session fixes its tools when it connects, so it cannot drop them for one
    step. A provider that reads files itself brings tools of its own, and can run a step
    tool-less only when it honors an empty tool list (the SDK does; Codex does not yet).
    Reading the capability, never the provider's name, covers a new provider without a
    change here. The message names the property that is missing.
    """
    if route is DispatchRoute.SESSION:
        missing = "it resolved to a persistent session, whose tool set is fixed at connect time"
    elif capabilities.can_read_files and not capabilities.honors_empty_tools:
        missing = f"the '{provider}' provider brings tools of its own and cannot run with none"
    else:
        return None
    return (
        f"Step '{step_name}' declares 'allowed_tools: []' but cannot be isolated on model "
        f"'{model}': {missing}. Use a model whose provider can run without tools, or remove "
        "'allowed_tools'."
    )


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
