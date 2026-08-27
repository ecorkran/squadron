"""Tests for the pure tool data types."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolResult


def test_tool_result_defaults_to_success() -> None:
    assert ToolResult("x").is_error is False


def test_tool_result_is_frozen() -> None:
    result = ToolResult("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.content = "y"  # type: ignore[misc]


def _probe_factory(cwd: Path) -> ToolExecutor:
    async def _execute(args: dict[str, object]) -> ToolResult:
        return ToolResult(f"{cwd}:{args}")

    return _execute


def test_descriptor_stores_fields_verbatim() -> None:
    schema: dict[str, object] = {"type": "object", "properties": {}}
    descriptor = ToolDescriptor(
        name="probe",
        description="a probe",
        parameters=schema,
        factory=_probe_factory,
    )

    assert descriptor.name == "probe"
    assert descriptor.description == "a probe"
    assert descriptor.parameters is schema
    assert descriptor.factory is _probe_factory


def test_descriptor_is_frozen() -> None:
    descriptor = ToolDescriptor("probe", "a probe", {}, _probe_factory)
    with pytest.raises(dataclasses.FrozenInstanceError):
        descriptor.name = "other"  # type: ignore[misc]


async def test_factory_returns_callable_executor(tmp_path: Path) -> None:
    descriptor = ToolDescriptor("probe", "a probe", {}, _probe_factory)

    executor = descriptor.factory(tmp_path)

    assert callable(executor)
    result = await executor({"k": "v"})
    assert str(tmp_path) in result.content
