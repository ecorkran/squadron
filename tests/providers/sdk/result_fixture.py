"""Build ``ResultMessage`` objects from the captured real CLI result (slice 175 Task 6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import ResultMessage

REAL_RESULT_PATH = Path(__file__).parent / "fixtures" / "result_message_real.json"


def real_result_fields() -> dict[str, Any]:
    """The captured result object; keys are the SDK's ``ResultMessage`` field names."""
    return json.loads(REAL_RESULT_PATH.read_text())


def real_result_message(**overrides: Any) -> ResultMessage:
    """A ``ResultMessage`` built from the real fixture, with fields optionally replaced."""
    fields = real_result_fields()
    fields.update(overrides)
    return ResultMessage(**fields)
