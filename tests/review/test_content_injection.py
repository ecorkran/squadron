"""Tests for _inject_file_contents() in review_client.py."""

from __future__ import annotations

from pathlib import Path

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
        "diff": "main",
        "files": "*.py",
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
