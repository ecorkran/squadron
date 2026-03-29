"""Shared pytest fixtures for the review module test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_sdk_client() -> MagicMock:
    """Mock ClaudeSDKClient at the import boundary.

    The mock supports context-manager usage and returns a configurable
    async iterator from ``receive_response()``.  Tests set the response
    content via ``mock.response_messages``.
    """
    client = MagicMock()
    client.response_messages: list[Any] = []

    # Support async context manager (async with ClaudeSDKClient(...) as c)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    # query() is awaitable
    client.query = AsyncMock()

    # receive_response() returns an async iterator over response_messages
    async def _receive_response():  # type: ignore[no-untyped-def]
        for msg in client.response_messages:
            yield msg

    client.receive_response = _receive_response

    return client


@pytest.fixture
def sample_review_result() -> dict[str, Any]:
    """Pre-built ReviewResult data for output/display tests.

    Returns a dict that can be unpacked into ReviewResult() once models exist.
    """
    from squadron.review.models import (
        ReviewFinding,
        ReviewResult,
        Severity,
        Verdict,
    )

    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="The runner does not handle SDK timeout errors.",
                file_ref="src/squadron/review/runner.py:42",
            ),
            ReviewFinding(
                severity=Severity.PASS,
                title="Clean module structure",
                description="Package layout follows project conventions.",
            ),
        ],
        raw_output="## Summary\nCONCERNS\n\n## Findings\n...",
        template_name="code",
        input_files={"cwd": "."},
    )


@pytest.fixture
def builtin_templates_dir() -> Path:
    """Path to the built-in templates directory."""
    from squadron.data import data_dir

    return data_dir() / "templates"
