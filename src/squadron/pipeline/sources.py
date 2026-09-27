"""Source registry for the ``each`` step type.

A source is named in pipeline YAML as ``namespace.function(args)`` — e.g.
``cf.unfinished_slices("{plan}")`` — and returns the list of items ``each``
iterates over. Each item is a dict bound to the step's ``as:`` name.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.integrations.context_forge import ContextForgeClient

SourceFn = Callable[
    [list[str], "ContextForgeClient", dict[str, object]],
    Awaitable[list[dict[str, object]]],
]

SOURCE_REGISTRY: dict[tuple[str, str], SourceFn] = {}

_SOURCE_RE = re.compile(r"(\w+)\.(\w+)\(([^)]*)\)")


async def _cf_unfinished_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
) -> list[dict[str, object]]:
    """Return slices whose status is not 'complete'."""
    slices = cf_client.list_slices()
    return [
        {
            "index": str(entry.index),
            "name": entry.name,
            "status": entry.status,
            "design_file": entry.design_file or "",
        }
        for entry in slices
        if entry.status != "complete"
    ]


SOURCE_REGISTRY[("cf", "unfinished_slices")] = _cf_unfinished_slices


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
