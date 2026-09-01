"""Tests for the squadron.tools public import surface."""

from __future__ import annotations

from pathlib import Path

from squadron import tools


def test_builtin_tools_are_registered() -> None:
    assert {"read_file", "write_file", "bash"} <= set(tools.list_tools())


def test_every_exported_name_is_accessible() -> None:
    for name in tools.__all__:
        assert hasattr(tools, name), f"{name} in __all__ but not on the package"


def test_materialize_binds_every_registered_tool(tmp_path: Path) -> None:
    registered = tools.list_tools()
    executors = tools.materialize(registered, tmp_path)

    assert set(executors) == set(registered)
    assert all(callable(ex) for ex in executors.values())
