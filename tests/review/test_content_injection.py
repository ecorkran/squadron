"""Tests for _inject_file_contents() in review_client.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.review.review_client import (
    _MAX_FILE_SIZE,
    _MAX_TOTAL_INJECTION,
    _inject_file_contents,
)

# ---------------------------------------------------------------------------
# Basic injection
# ---------------------------------------------------------------------------


def test_file_contents_appear_in_prompt(tmp_path: Path) -> None:
    """File contents from inputs are injected into the prompt."""
    file_a = tmp_path / "design.md"
    file_a.write_text("# Slice Design\nSome content here.")

    prompt = "Review the following document: {input}"
    inputs = {"input": str(file_a), "cwd": str(tmp_path)}

    result = _inject_file_contents(prompt, inputs)
    assert "## File Contents" in result
    assert "# Slice Design" in result
    assert "Some content here." in result


def test_cwd_key_is_skipped(tmp_path: Path) -> None:
    """The cwd key is skipped even if its value is a valid file path."""
    # Create a file that cwd points to (unlikely but possible)
    cwd_file = tmp_path / "cwd"
    cwd_file.write_text("should not appear")

    prompt = "Review this"
    inputs = {"cwd": str(cwd_file)}

    result = _inject_file_contents(prompt, inputs)
    assert result == prompt  # no injection
    assert "should not appear" not in result


def test_nonexistent_file_is_skipped() -> None:
    """Non-existent file paths are skipped without error."""
    prompt = "Review this"
    inputs = {"input": "/nonexistent/path/to/file.md", "cwd": "."}

    result = _inject_file_contents(prompt, inputs)
    assert result == prompt


def test_non_file_values_are_skipped(tmp_path: Path) -> None:
    """Non-file values like directories or bare strings are skipped."""
    prompt = "Review this"
    inputs = {
        "cwd": str(tmp_path),
        "some_key": "not-a-file",
    }

    result = _inject_file_contents(prompt, inputs)
    assert result == prompt


# ---------------------------------------------------------------------------
# Size limits
# ---------------------------------------------------------------------------


def test_large_file_is_truncated(tmp_path: Path) -> None:
    """Files exceeding _MAX_FILE_SIZE are truncated with a message."""
    large_file = tmp_path / "big.md"
    content = "x" * (_MAX_FILE_SIZE + 10_000)
    large_file.write_text(content)

    prompt = "Review this"
    inputs = {"input": str(large_file)}

    result = _inject_file_contents(prompt, inputs)
    assert "truncated" in result.lower()
    assert "file too large" in result.lower()
    # Truncated content should not exceed limit + truncation message
    assert len(result) < _MAX_FILE_SIZE + 500


def test_total_injection_capped(tmp_path: Path) -> None:
    """Total injection is capped at _MAX_TOTAL_INJECTION."""
    # Create multiple files that together exceed the limit
    per_file = _MAX_TOTAL_INJECTION // 3
    files: dict[str, str] = {}
    for i in range(5):
        f = tmp_path / f"file{i}.md"
        f.write_text("y" * per_file)
        files[f"input{i}"] = str(f)

    prompt = "Review this"
    result = _inject_file_contents(prompt, files)

    # Should have some files but not all (total limit reached)
    injected_count = result.count("### input")
    assert injected_count < 5
    assert injected_count >= 1


# ---------------------------------------------------------------------------
# Multiple files
# ---------------------------------------------------------------------------


def test_multiple_files_injected(tmp_path: Path) -> None:
    """Multiple input files are all injected."""
    file_a = tmp_path / "tasks.md"
    file_a.write_text("# Tasks\nTask content.")
    file_b = tmp_path / "design.md"
    file_b.write_text("# Design\nDesign content.")

    prompt = "Review these"
    inputs = {
        "input": str(file_a),
        "against": str(file_b),
        "cwd": str(tmp_path),
    }

    result = _inject_file_contents(prompt, inputs)
    assert "Task content." in result
    assert "Design content." in result
    assert result.count("### ") == 2  # two file sections


# ---------------------------------------------------------------------------
# Git diff injection
# ---------------------------------------------------------------------------


def test_diff_input_triggers_git_diff() -> None:
    """diff input triggers git diff subprocess."""
    prompt = "Review code"
    inputs = {"diff": "main", "cwd": "."}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "diff --git a/foo.py\n+new line"
        _inject_file_contents(prompt, inputs)

    mock_run.assert_called_once()
    args = mock_run.call_args
    assert args[0][0] == ["git", "diff", "main"]


def test_diff_output_in_prompt() -> None:
    """Diff output appears in the enriched prompt."""
    prompt = "Review code"
    inputs = {"diff": "main", "cwd": "."}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "diff --git a/foo.py\n+added line"
        result = _inject_file_contents(prompt, inputs)

    assert "Git Diff" in result
    assert "+added line" in result


def test_large_diff_is_truncated() -> None:
    """Large diffs are truncated at _MAX_FILE_SIZE."""
    prompt = "Review code"
    inputs = {"diff": "main", "cwd": "."}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "x" * (_MAX_FILE_SIZE + 5000)
        result = _inject_file_contents(prompt, inputs)

    assert "truncated" in result.lower()


def test_diff_failure_is_skipped() -> None:
    """Failed git diff is silently skipped."""
    prompt = "Review code"
    inputs = {"diff": "nonexistent-ref", "cwd": "."}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stderr = "fatal: bad ref"
        mock_run.return_value.stdout = ""
        result = _inject_file_contents(prompt, inputs)

    assert result == prompt


# ---------------------------------------------------------------------------
# Files glob injection
# ---------------------------------------------------------------------------


def test_files_glob_resolves_and_injects(tmp_path: Path) -> None:
    """files glob input resolves and injects matching file contents."""
    (tmp_path / "a.py").write_text("print('a')")
    (tmp_path / "b.py").write_text("print('b')")
    (tmp_path / "c.txt").write_text("not matching")

    prompt = "Review code"
    inputs = {"files": "*.py", "cwd": str(tmp_path)}

    result = _inject_file_contents(prompt, inputs)
    assert "print('a')" in result
    assert "print('b')" in result
    assert "not matching" not in result


# ---------------------------------------------------------------------------
# Integration test — full non-SDK review path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_sdk_review_injects_file_contents(tmp_path: Path) -> None:
    """Full path: alias resolution → content injection → enriched prompt
    reaches the API with file contents, not just paths."""
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import InputDef, ReviewTemplate

    # Create test files
    task_file = tmp_path / "tasks.md"
    task_file.write_text("# Tasks\n- [ ] Implement feature X")
    design_file = tmp_path / "design.md"
    design_file.write_text("# Design\nFeature X overview")

    template = ReviewTemplate(
        name="tasks",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=[],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[
            InputDef(name="input", description="doc"),
            InputDef(name="against", description="ref"),
        ],
        optional_inputs=[
            InputDef(name="cwd", description="dir", default="."),
        ],
        prompt_template="Review {input} against {against}",
        profile=None,
        model=None,
    )

    inputs = {
        "input": str(task_file),
        "against": str(design_file),
        "cwd": str(tmp_path),
    }

    # Mock the provider profile, API key, and OpenAI client
    mock_profile = AsyncMock()
    mock_profile.name = "openai"
    mock_profile.base_url = None
    mock_profile.default_headers = None
    mock_profile.api_key_env = "OPENAI_API_KEY"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = (
        "## Summary\nPASS\n\n## Findings\n\n### [PASS] Coverage\nAll tasks covered."
    )

    captured_messages: list[object] = []

    async def capture_create(**kwargs: object) -> object:
        captured_messages.append(kwargs.get("messages"))
        return mock_response

    mock_client = AsyncMock()
    mock_client.chat.completions.create = capture_create

    with (
        patch(
            "squadron.review.review_client.get_profile",
            return_value=mock_profile,
        ),
        patch(
            "squadron.review.review_client._resolve_api_key",
            return_value="fake-key",
        ),
        patch(
            "squadron.review.review_client.AsyncOpenAI",
            return_value=mock_client,
        ),
    ):
        result = await run_review_with_profile(
            template,
            inputs,
            profile="openai",
            model="gpt-4o",
        )

    # Verify file contents were injected into the prompt
    assert len(captured_messages) == 1
    messages = captured_messages[0]
    user_prompt = messages[1]["content"]  # type: ignore[index]

    # The prompt should contain actual file contents, not just paths
    assert "Implement feature X" in user_prompt
    assert "Feature X overview" in user_prompt
    assert "## File Contents" in user_prompt
    assert result.verdict is not None
