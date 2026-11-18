"""Read an ``sq review code --output file`` JSON document into recall parts (slice 430 D4).

The hand-run grid files and a live review stage's output file share this format, so the
import and the stage runner read findings and usage through this one module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from squadron.core.models import Effort
from squadron.core.usage import CostBasis
from squadron.metrology.recall_run_models import RecallFinding, StageUsage, content_key
from squadron.metrology.review_category_map import map_historical_category

FINDING_ID_PREFIX = "F"


class ReviewOutputError(ValueError):
    """The document lacks a field the reader needs, or a field has the wrong shape."""


def finding_id_at(index: int) -> str:
    """The positional finding id of the finding at *index* (0-based) in ``findings``."""
    return f"{FINDING_ID_PREFIX}{index + 1}"


def read_findings(data: Mapping[str, Any]) -> tuple[RecallFinding, ...]:
    """Every finding in ``findings``, in order, ids positional (``F1`` is index 0)."""
    raw = data.get("findings")
    if not isinstance(raw, list):
        raise ReviewOutputError("missing field 'findings' (a list)")
    items = cast(list[object], raw)
    return tuple(_finding(index, item) for index, item in enumerate(items))


def _finding(index: int, item: object) -> RecallFinding:
    if not isinstance(item, dict):
        raise ReviewOutputError(f"finding {index} is not an object")
    fields = cast(dict[str, Any], item)
    for name in ("severity", "title", "description"):
        if not isinstance(fields.get(name), str):
            raise ReviewOutputError(f"finding {index} lacks string field {name!r}")
    location = fields.get("location")
    location = location if isinstance(location, str) else None
    normalized = map_historical_category(_opt_str(fields, "category"))
    return RecallFinding(
        finding_id=finding_id_at(index),
        content_key=content_key(location, fields["title"], fields["description"]),
        severity=fields["severity"],
        category=normalized.category,
        raw_category=_opt_str(fields, "raw_category") or normalized.raw_category,
        location=location,
        title=fields["title"],
        description=fields["description"],
    )


def read_usage(data: Mapping[str, Any]) -> StageUsage:
    """Cost, basis, duration, turns and tool calls; an absent or malformed field is ``None``."""
    basis = _opt_str(data, "cost_basis")
    return StageUsage(
        cost_usd=_opt_number(data, "cost_usd"),
        cost_basis=CostBasis(basis) if basis in CostBasis.__members__.values() else None,
        duration_s=_opt_number(data, "duration_seconds"),
        turns=_opt_int(data, "turns"),
        tool_calls=_opt_int(data, "tool_calls_made"),
    )


def read_effort(data: Mapping[str, Any]) -> Effort | None:
    """The output's ``effort`` field as an ``Effort``; an unknown word raises."""
    value = _opt_str(data, "effort")
    if value is None:
        return None
    try:
        return Effort(value)
    except ValueError as exc:
        raise ReviewOutputError(f"unknown effort {value!r}") from exc


def _opt_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and value else None


def _opt_int(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _opt_number(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
