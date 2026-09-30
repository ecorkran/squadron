"""Tests for the tool-use guidance block composition (slice 267, SC2)."""

from __future__ import annotations

from squadron.tools import compose_system_prompt
from squadron.tools.guidance import TOOL_USE_HEADING


def test_no_instructions_no_tools_returns_none() -> None:
    assert compose_system_prompt(None, None) is None


def test_empty_tool_list_leaves_instructions_unchanged() -> None:
    assert compose_system_prompt("x", []) == "x"


def test_none_tool_list_leaves_instructions_unchanged() -> None:
    assert compose_system_prompt("x", None) == "x"


def test_instructions_precede_the_block() -> None:
    composed = compose_system_prompt("x", ["read_file", "grep"])

    assert composed is not None
    assert composed.startswith("x")
    # Position, not mere presence: SC2 requires the caller's instructions to come first.
    assert composed.index("x") < composed.index(TOOL_USE_HEADING)


def test_effective_tool_names_are_rendered_into_the_block() -> None:
    composed = compose_system_prompt("x", ["read_file", "grep"])

    assert composed is not None
    assert "read_file" in composed
    assert "grep" in composed


def test_block_stands_alone_without_instructions() -> None:
    composed = compose_system_prompt(None, ["read_file"])

    assert composed is not None
    assert composed.startswith(TOOL_USE_HEADING)


def test_empty_instructions_yield_the_block_alone() -> None:
    composed = compose_system_prompt("", ["read_file"])

    assert composed is not None
    assert composed.startswith(TOOL_USE_HEADING)


def test_block_does_not_name_tools_outside_the_effective_list() -> None:
    """The prose is tool-agnostic (D1): only the rendered names appear."""
    composed = compose_system_prompt(None, ["read_file"])

    assert composed is not None
    assert "write_file" not in composed
    assert "list_files" not in composed


_BATCHING = (
    "When you already know several files you need, request them together — in one call if "
    "the\ntool accepts several paths, and as parallel tool calls in one turn otherwise. "
    "Every turn\nresends the whole conversation, so one file per turn is the slowest way "
    "to read."
)


def test_block_asks_for_batched_reads_without_naming_a_tool() -> None:
    """Slice 931 D7: the batching paragraph, beside the do-not-over-read sentence."""
    composed = compose_system_prompt(None, ["list_files"])

    assert composed is not None
    assert _BATCHING in composed
    assert "Do not read files a\nclaim does not depend on" in composed
    for name in ("read_file", "grep", "write_file"):
        assert name not in composed.split("\n", 2)[2].replace("list_files", "")
