"""Tests for reading token usage off OpenAI-shaped stream chunks (slice 931 D8, D12)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.core.usage import TokenUsage
from squadron.providers.openai.usage import read_chunk_usage

from .conftest import text_chunk, usage_chunk

_FULL: dict[str, object] = {
    "prompt_tokens": 100,
    "completion_tokens": 20,
    "total_tokens": 120,
    "prompt_tokens_details": {"cached_tokens": 60},
    "completion_tokens_details": {"reasoning_tokens": 7},
}


def test_chunk_without_usage_returns_none() -> None:
    assert read_chunk_usage(text_chunk("hi")) is None


@pytest.mark.parametrize("openrouter_shape", [False, True], ids=["openai-ollama", "openrouter"])
def test_both_chunk_shapes_read_every_field(openrouter_shape: bool) -> None:
    chunk = usage_chunk(_FULL, openrouter_shape=openrouter_shape)

    assert read_chunk_usage(chunk) == TokenUsage(prompt=100, cached=60, completion=20, reasoning=7)


def test_ollama_shape_without_completion_details_leaves_reasoning_none() -> None:
    chunk = usage_chunk(
        {
            "prompt_tokens": 50,
            "completion_tokens": 5,
            "total_tokens": 55,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
    )

    assert read_chunk_usage(chunk) == TokenUsage(prompt=50, cached=0, completion=5, reasoning=None)


@pytest.mark.parametrize(
    ("override", "field_name", "expected"),
    [
        (
            {"prompt_tokens": "lots"},
            "prompt_tokens",
            TokenUsage(prompt=None, cached=60, completion=20, reasoning=7),
        ),
        (
            {"completion_tokens": 2.5},
            "completion_tokens",
            TokenUsage(prompt=100, cached=60, completion=None, reasoning=7),
        ),
        (
            {"prompt_tokens_details": [60]},
            "prompt_tokens_details.cached_tokens",
            TokenUsage(prompt=100, cached=None, completion=20, reasoning=7),
        ),
        (
            {"completion_tokens_details": {"reasoning_tokens": "seven"}},
            "completion_tokens_details.reasoning_tokens",
            TokenUsage(prompt=100, cached=60, completion=20, reasoning=None),
        ),
    ],
    ids=["str-count", "float-count", "list-details", "str-detail-count"],
)
def test_malformed_field_is_none_siblings_intact_and_warned(
    override: dict[str, object],
    field_name: str,
    expected: TokenUsage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    chunk = usage_chunk({**_FULL, **override})

    with caplog.at_level(logging.WARNING):
        result = read_chunk_usage(chunk)

    assert result == expected
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert field_name in warnings[0].getMessage()


def test_without_warned_set_every_malformed_field_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chunk = usage_chunk({**_FULL, "prompt_tokens": "x", "completion_tokens": "y"})

    with caplog.at_level(logging.WARNING):
        read_chunk_usage(chunk)
        read_chunk_usage(chunk)

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 4


def test_shared_warned_set_logs_each_field_once(caplog: pytest.LogCaptureFixture) -> None:
    warned: set[str] = set()
    chunk = usage_chunk({**_FULL, "prompt_tokens": "x"})

    with caplog.at_level(logging.WARNING):
        read_chunk_usage(chunk, warned=warned)
        read_chunk_usage(chunk, warned=warned)

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
    assert warned == {"prompt_tokens"}


def test_core_usage_imports_no_openai_types() -> None:
    import squadron.core.usage as core_usage

    imports = [
        line
        for line in Path(core_usage.__file__).read_text().splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert not [line for line in imports if "openai" in line or "squadron" in line]
