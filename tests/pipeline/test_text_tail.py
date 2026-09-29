"""Tests for the shared final-text tail (slice 932 D6/D7)."""

from __future__ import annotations

from squadron.pipeline.text_tail import FINAL_TEXT_TAIL_CHARS, tail_text


def test_empty_input_renders_placeholder() -> None:
    assert tail_text("") == "(empty response)"
    assert tail_text("  \n\t ") == "(empty response)"


def test_short_input_is_kept_without_mark() -> None:
    assert tail_text("the agent is still running.") == "the agent is still running."


def test_long_input_keeps_last_chars_with_mark() -> None:
    text = "a" * 50 + "b" * FINAL_TEXT_TAIL_CHARS
    assert tail_text(text) == "…" + "b" * FINAL_TEXT_TAIL_CHARS


def test_whitespace_is_collapsed() -> None:
    assert tail_text("one\n\n  two\tthree ") == "one two three"
