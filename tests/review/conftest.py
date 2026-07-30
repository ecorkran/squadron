"""Shared pytest fixtures for the review module test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.review.git_utils import DEFAULT_DIFF_BASE


@pytest.fixture(autouse=True)
def _isolated_user_config(tmp_path: Path) -> Iterator[Path]:
    """Redirect the user-level config file to an empty temp file.

    Without this, a developer's real ``~/.config/squadron/config.toml``
    leaks into every test that reads config. The size-cap tests are the
    ones that actually break: they size their fixtures from the *default*
    ``review.max_file_size_bytes`` while the code resolves the user's
    override, so a raised local cap silently stops the file from being
    large enough to truncate. Mirrors the same fixture in
    ``tests/metrology/conftest.py``.
    """
    user_file = tmp_path / "user-config" / "config.toml"
    user_file.parent.mkdir(parents=True, exist_ok=True)
    with patch("squadron.config.manager.user_config_path", return_value=user_file):
        yield user_file


@pytest.fixture(autouse=True)
def _pinned_diff_base() -> Iterator[str]:
    """Pin the slice diff base so tests never read live CF config.

    ``resolve_slice_diff_range(n, cwd)`` resolves its base by shelling out
    to ``cf config get git.integration_branch``, so without this any test
    that resolves a diff range inherits whatever the developer's machine
    has configured — passing on a repo that leaves the key empty and
    failing on one that sets it. Same class of leak as
    ``_isolated_user_config`` above.

    Tests that exercise base resolution deliberately either patch
    ``resolve_diff_base`` themselves or pass ``base=`` explicitly, both of
    which bypass this fixture.
    """
    with patch(
        "squadron.review.git_utils.resolve_diff_base",
        return_value=DEFAULT_DIFF_BASE,
    ):
        yield DEFAULT_DIFF_BASE


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


@pytest.fixture
def doc_files(tmp_path: Path) -> tuple[str, str]:
    """Real (input, against) document paths for CLI review invocations.

    The input/against existence guard (issue #18) rejects paths that name
    no real file, so tests driving review commands must point at files
    that exist.
    """
    input_doc = tmp_path / "input-doc.md"
    against_doc = tmp_path / "against-doc.md"
    input_doc.write_text("# input document\n")
    against_doc.write_text("# against document\n")
    return str(input_doc), str(against_doc)
