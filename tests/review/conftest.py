"""Shared pytest fixtures for the review module test suite."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.review.git_utils import DEFAULT_DIFF_BASE


@pytest.fixture(autouse=True)
def _pinned_diff_base() -> Iterator[str]:
    """Pin the slice diff base so tests never read live CF config.

    ``resolve_slice_diff_range(n, cwd)`` resolves its base by shelling out
    to ``cf config get git.integration_branch``, so without this any test
    that resolves a diff range inherits whatever the developer's machine
    has configured — passing on a repo that leaves the key empty and
    failing on one that sets it. The per-test home in the root conftest
    cannot cover this: cf reads the checkout's project config, not ``HOME``.

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
def git_repo(tmp_path: Path) -> Path:
    """A temporary git repo with one commit, so HEAD resolves."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True
    )
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


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
