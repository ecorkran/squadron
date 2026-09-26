"""Tests for answers_as_requested (slice 927 D9)."""

import pytest

from squadron.models.snapshot import answers_as_requested


@pytest.mark.parametrize(
    ("requested", "answered"),
    [
        ("claude-x", "claude-x"),
        ("claude-x", "claude-x-20251001"),
        ("gpt-5", "gpt-5-2025-08-07"),
        ("anthropic/claude-x", "anthropic/claude-x-20260101"),
    ],
)
def test_answers_as_requested_true(requested: str, answered: str) -> None:
    assert answers_as_requested(requested, answered) is True


@pytest.mark.parametrize(
    ("requested", "answered"),
    [
        ("gpt-5", "gpt-5-mini"),
        ("gpt-5", "gpt-4.1"),
        ("claude-x", "claude-x-2025"),
        ("a.b", "axb"),
    ],
)
def test_answers_as_requested_false(requested: str, answered: str) -> None:
    assert answers_as_requested(requested, answered) is False
