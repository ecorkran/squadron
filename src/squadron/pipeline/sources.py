"""Source registry for the ``each`` step type.

A source is named in pipeline YAML as ``namespace.function(args)`` — e.g.
``cf.unfinished_slices("{plan}")`` — and returns the list of items ``each``
iterates over. Each item is a dict bound to the step's ``as:`` name.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.integrations.context_forge import ContextForgeClient, SliceEntry

SourceFn = Callable[
    [list[str], "ContextForgeClient", dict[str, object]],
    Awaitable[list[dict[str, object]]],
]

SOURCE_REGISTRY: dict[tuple[str, str], SourceFn] = {}

_SOURCE_RE = re.compile(r"(\w+)\.(\w+)\(([^)]*)\)")


class CfSliceStatus(StrEnum):
    """cf slice statuses a source selects on (slice 195 D1)."""

    COMPLETE = "complete"
    DEFERRED = "deferred"


_EXCLUDED_STATUSES = frozenset({CfSliceStatus.COMPLETE, CfSliceStatus.DEFERRED})


def _plan_arg(args: list[str]) -> str | None:
    """The source's ``plan`` argument as a cf arch index, or None when absent.

    Raises ValueError when the value is not all digits — a slice-plan name or
    an unresolved ``{plan}`` placeholder would otherwise reach cf as garbage.
    """
    if not args:
        return None
    plan = args[0]
    if not plan.isdigit():
        raise ValueError(f"plan must be an architecture index, got {plan!r}")
    return plan


def _slice_item(entry: SliceEntry) -> dict[str, object]:
    return {
        "index": str(entry.index),
        "name": entry.name,
        "status": entry.status,
        "design_file": entry.design_file or "",
    }


async def _cf_unfinished_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
) -> list[dict[str, object]]:
    """Return slices of the plan whose status is not 'complete'."""
    slices = cf_client.list_slices(_plan_arg(args))
    return [_slice_item(entry) for entry in slices if entry.status != CfSliceStatus.COMPLETE]


async def _cf_undesigned_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
) -> list[dict[str, object]]:
    """Return open slices of the plan that have no design file yet."""
    slices = cf_client.list_slices(_plan_arg(args))
    return [
        _slice_item(entry)
        for entry in slices
        if entry.status not in _EXCLUDED_STATUSES and not entry.design_file
    ]


SOURCE_REGISTRY[("cf", "unfinished_slices")] = _cf_unfinished_slices
SOURCE_REGISTRY[("cf", "undesigned_slices")] = _cf_undesigned_slices


def parse_source(
    source_str: str,
) -> tuple[str, str, list[str]]:
    """Parse a source string like ``cf.unfinished_slices("{plan}")``.

    Returns (namespace, function, args_list).
    Raises ValueError for unknown namespace/function combinations.
    """
    match = _SOURCE_RE.fullmatch(source_str.strip())
    if not match:
        raise ValueError(
            f"Invalid source string {source_str!r}. Expected format: namespace.function(args)"
        )
    namespace = match.group(1)
    function = match.group(2)
    args_raw = match.group(3).strip()
    args = [a.strip().strip("\"'") for a in args_raw.split(",") if a.strip()] if args_raw else []

    key = (namespace, function)
    if key not in SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source '{namespace}.{function}'. Registered sources: {list(SOURCE_REGISTRY)}"
        )
    return namespace, function, args
