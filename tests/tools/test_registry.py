"""Tests for the tool registry."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.tools import registry
from squadron.tools.errors import ToolNotRegisteredError
from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolResult


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[None]:
    """Snapshot and restore the module-level registry.

    Built-in tools register at package import, so tests that register doubles would otherwise
    leak into every other test module — or collide with the built-in names.
    """
    snapshot = dict(registry._REGISTRY)
    try:
        yield
    finally:
        registry._REGISTRY.clear()
        registry._REGISTRY.update(snapshot)


def _make_descriptor(name: str, recorder: list[Path] | None = None) -> ToolDescriptor:
    def factory(cwd: Path) -> ToolExecutor:
        if recorder is not None:
            recorder.append(cwd)

        async def _execute(args: dict[str, object]) -> ToolResult:
            return ToolResult(f"{name}:{args}")

        return _execute

    return ToolDescriptor(name=name, description=f"probe {name}", parameters={}, factory=factory)


def test_register_then_lookup_returns_same_descriptor() -> None:
    descriptor = _make_descriptor("probe")
    registry.register(descriptor)

    assert registry.lookup("probe") is descriptor


def test_register_duplicate_name_raises_value_error() -> None:
    registry.register(_make_descriptor("probe"))

    with pytest.raises(ValueError, match="probe"):
        registry.register(_make_descriptor("probe"))


def test_lookup_unknown_returns_none() -> None:
    assert registry.lookup("nope") is None


def test_list_tools_includes_registered_name() -> None:
    registry.register(_make_descriptor("probe"))

    assert "probe" in registry.list_tools()


def test_materialize_returns_callables_keyed_by_name(tmp_path: Path) -> None:
    registry.register(_make_descriptor("probe_a"))
    registry.register(_make_descriptor("probe_b"))

    executors = registry.materialize(["probe_a", "probe_b"], tmp_path)

    assert set(executors) == {"probe_a", "probe_b"}
    assert all(callable(ex) for ex in executors.values())


def test_materialize_unknown_name_raises_naming_offender_and_available(tmp_path: Path) -> None:
    registry.register(_make_descriptor("probe"))

    with pytest.raises(ToolNotRegisteredError) as excinfo:
        registry.materialize(["nope"], tmp_path)

    message = str(excinfo.value)
    assert "nope" in message
    assert "probe" in message


def test_materialize_resolves_cwd_before_handing_it_to_factories(tmp_path: Path) -> None:
    recorder: list[Path] = []
    registry.register(_make_descriptor("probe", recorder))
    unresolved = tmp_path / "sub" / ".." / "sub"
    (tmp_path / "sub").mkdir()

    registry.materialize(["probe"], unresolved)

    assert recorder == [unresolved.resolve()]
    assert ".." not in str(recorder[0])
