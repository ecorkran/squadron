"""Tests for _inject_file_contents() in review_client.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.review.review_client import (
    _MAX_FILE_SIZE,
    _MAX_TOTAL_INJECTION,
    _demote_headings,
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


def test_nonexistent_file_is_skipped(tmp_path: Path) -> None:
    """Non-existent file paths are skipped without error."""
    prompt = "Review this"
    inputs = {"input": "/nonexistent/path/to/file.md", "cwd": str(tmp_path)}

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
    inputs = {"input": str(large_file), "cwd": str(tmp_path)}

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


def test_large_diff_is_truncated(tmp_path: Path) -> None:
    """Large diffs are truncated at _MAX_FILE_SIZE."""
    prompt = "Review code"
    inputs = {"diff": "main", "cwd": str(tmp_path)}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "x" * (_MAX_FILE_SIZE + 5000)
        result = _inject_file_contents(prompt, inputs)

    assert "truncated" in result.lower()


def test_diff_failure_is_skipped(tmp_path: Path) -> None:
    """Failed git diff is silently skipped."""
    prompt = "Review code"
    inputs = {"diff": "nonexistent-ref", "cwd": str(tmp_path)}

    with patch("squadron.review.review_client.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stderr = "fatal: bad ref"
        mock_run.return_value.stdout = ""
        result = _inject_file_contents(prompt, inputs)

    assert result == prompt


# ---------------------------------------------------------------------------
# Heading demotion
# ---------------------------------------------------------------------------


def test_demote_headings_shifts_by_two() -> None:
    """H1→H3, H2→H4, H3→H5 with default levels=2."""
    content = "# Title\n## Section\n### Sub\nPlain text."
    result = _demote_headings(content, levels=2)
    assert result == "### Title\n#### Section\n##### Sub\nPlain text."


def test_demote_headings_clamps_at_h6() -> None:
    """Headings that would exceed H6 are clamped to H6."""
    content = "##### Deep\n###### Already max"
    result = _demote_headings(content, levels=2)
    assert result == "###### Deep\n###### Already max"


def test_demote_headings_leaves_non_headings_unchanged() -> None:
    """Lines that are not headings pass through unmodified."""
    content = "Normal line\n  # indented (not a heading)\n#NoSpace"
    result = _demote_headings(content, levels=2)
    # Only ATX headings at column 0 with a space after # are demoted
    assert "Normal line" in result
    assert "  # indented (not a heading)" in result
    assert "#NoSpace" in result


def test_demote_headings_empty_string() -> None:
    """Empty input returns empty output without error."""
    assert _demote_headings("", levels=2) == ""


def test_demote_headings_levels_zero() -> None:
    """levels=0 returns content unchanged."""
    content = "# Title\n## Section"
    assert _demote_headings(content, levels=0) == content


# ---------------------------------------------------------------------------
# CLAUDE.md injection
# ---------------------------------------------------------------------------


def test_claude_md_injected_when_present(tmp_path: Path) -> None:
    """CLAUDE.md in cwd is injected so API-only models can read conventions."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project conventions\nNo magic defaults.")

    prompt = "Review code"
    inputs = {"cwd": str(tmp_path)}

    result = _inject_file_contents(prompt, inputs)
    assert "CLAUDE.md (project conventions)" in result
    assert "No magic defaults." in result


def test_claude_md_headings_are_demoted(tmp_path: Path) -> None:
    """CLAUDE.md H1/H2 headings are demoted by 2 levels on injection."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Core Principles\n## Code Style\n### Detail")

    result = _inject_file_contents("Review", {"cwd": str(tmp_path)})
    assert "### Core Principles" in result
    assert "#### Code Style" in result
    assert "##### Detail" in result
    # Original H1 must not appear
    assert "\n# Core Principles" not in result


def test_claude_md_absent_is_silently_skipped(tmp_path: Path) -> None:
    """No CLAUDE.md in cwd → no injection, no error."""
    prompt = "Review code"
    inputs = {"cwd": str(tmp_path)}

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
    """Full path: content injection → enriched prompt reaches the agent
    with file contents, not just paths."""
    from collections.abc import AsyncIterator
    from unittest.mock import MagicMock

    from squadron.core.models import AgentState, Message, MessageType
    from squadron.providers.base import ProviderCapabilities
    from squadron.providers.profiles import ProviderProfile
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

    # Capture the prompt sent to the agent
    captured_prompts: list[str] = []
    review_output = (
        "## Summary\nPASS\n\n## Findings\n\n### [PASS] Coverage\nAll tasks covered."
    )

    mock_agent = MagicMock()
    mock_agent.state = AgentState.idle
    mock_agent.shutdown = AsyncMock()

    async def capture_handle(message: Message) -> AsyncIterator[Message]:
        captured_prompts.append(message.content)
        yield Message(
            sender="mock",
            recipients=[],
            content=review_output,
            message_type=MessageType.chat,
        )

    mock_agent.handle_message = capture_handle

    mock_provider = MagicMock()
    mock_provider.capabilities = ProviderCapabilities(can_read_files=False)
    mock_provider.create_agent = AsyncMock(return_value=mock_agent)

    with (
        patch(
            "squadron.review.review_client.get_profile",
            return_value=ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            ),
        ),
        patch("squadron.review.review_client.get_provider", return_value=mock_provider),
        patch("squadron.review.review_client.ensure_provider_loaded"),
    ):
        result = await run_review_with_profile(
            template,
            inputs,
            profile="openai",
            model="gpt-4o",
        )

    # Verify file contents were injected into the prompt
    assert len(captured_prompts) == 1
    user_prompt = captured_prompts[0]
    assert "Implement feature X" in user_prompt
    assert "Feature X overview" in user_prompt
    assert "## File Contents" in user_prompt
    assert result.verdict is not None
