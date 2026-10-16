"""JSON-ready values for the stats reports (slice 176 API contracts).

Each report's ``to_json_dict()`` serializes its dataclass fields through here, so a table
and its ``--json`` read the same values. Keys are the field names, not a stable contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import cast


def to_json_value(value: object) -> object:
    """Dataclasses become dicts of their fields; times, enums and paths become plain values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return {str(key): to_json_value(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        return [to_json_value(item) for item in cast("list[object] | tuple[object, ...]", value)]
    return value


def to_json_dict(report: object) -> dict[str, object]:
    """A report dataclass as a dict of its serialized fields."""
    converted = to_json_value(report)
    if not isinstance(converted, dict):
        raise TypeError(f"{type(report).__name__} is not a dataclass")
    return cast("dict[str, object]", converted)
