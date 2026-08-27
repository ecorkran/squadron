"""Tests for the squadron.tools public import surface."""

from __future__ import annotations

from pathlib import Path

from squadron import tools


def test_exactly_the_three_builtin_tools_are_registered() -> None:
    assert set(tools.list_tools()) == {"read_file", "write_file", "bash"}


def test_every_exported_name_is_accessible() -> None:
    for name in tools.__all__:
        assert hasattr(tools, name), f"{name} in __all__ but not on the package"


def test_materialize_binds_every_registered_tool(tmp_path: Path) -> None:
    executors = tools.materialize(tools.list_tools(), tmp_path)

    assert len(executors) == 3
    assert all(callable(ex) for ex in executors.values())
