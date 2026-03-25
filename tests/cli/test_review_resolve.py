"""Tests for CLI slice number resolution in review commands."""

from __future__ import annotations

from unittest.mock import patch

import click.exceptions
import pytest

from squadron.cli.commands.review import _resolve_slice_number
from squadron.integrations.context_forge import (
    ContextForgeNotAvailable,
    ProjectInfo,
    SliceEntry,
    TaskEntry,
)

# ---------------------------------------------------------------------------
# Sample typed fixtures (matching ContextForgeClient return types)
# ---------------------------------------------------------------------------

SLICE_ENTRIES = [
    SliceEntry(
        index=118,
        name="Claude Code Commands — Composed Workflows",
        design_file="project-documents/user/slices/118-slice.composed-workflows.md",
        status="complete",
    ),
    SliceEntry(
        index=119,
        name="Conversation Persistence",
        design_file=None,
        status="not_started",
    ),
]

TASK_ENTRIES = [
    TaskEntry(index=118, files=["118-tasks.composed-workflows.md"]),
]

PROJECT_INFO = ProjectInfo(
    arch_file="project-documents/user/architecture/100-arch.orchestration-v2.md",
    slice_plan="100-slices.orchestration-v2",
    phase="Phase 6: Implementation",
    slice="118-slice.composed-workflows",
)


def _patch_client():  # type: ignore[no-untyped-def]
    """Patch ContextForgeClient with canned typed data."""
    return patch(
        "squadron.cli.commands.review.ContextForgeClient",
        **{
            "return_value.list_slices.return_value": SLICE_ENTRIES,
            "return_value.list_tasks.return_value": TASK_ENTRIES,
            "return_value.get_project.return_value": PROJECT_INFO,
        },
    )


# ---------------------------------------------------------------------------
# _resolve_slice_number tests
# ---------------------------------------------------------------------------


def test_resolve_valid_slice() -> None:
    """Resolves a known slice number to correct paths."""
    with _patch_client():
        info = _resolve_slice_number("118")
        assert info["index"] == 118
        assert info["slice_name"] == "composed-workflows"
        assert info["design_file"] == (
            "project-documents/user/slices/118-slice.composed-workflows.md"
        )
        assert info["task_files"] == ["118-tasks.composed-workflows.md"]
        assert info["arch_file"] == (
            "project-documents/user/architecture/100-arch.orchestration-v2.md"
        )


def test_resolve_slice_no_design_file() -> None:
    """Resolves a slice with null designFile — slice_name derived from entry name."""
    with _patch_client():
        info = _resolve_slice_number("119")
        assert info["index"] == 119
        assert info["design_file"] is None
        assert info["slice_name"] == "conversation-persistence"


def test_resolve_slice_not_found() -> None:
    """Exits with error when slice number doesn't exist."""
    with _patch_client():
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _resolve_slice_number("999")


def test_resolve_slice_cf_not_installed() -> None:
    """Exits with error when cf CLI is not available."""
    with patch(
        "squadron.cli.commands.review.ContextForgeClient",
    ) as mock_cls:
        mock_cls.return_value.list_slices.side_effect = ContextForgeNotAvailable(
            "cf not found"
        )
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _resolve_slice_number("118")


# ---------------------------------------------------------------------------
# Command integration (verify digit detection routes through resolver)
# ---------------------------------------------------------------------------


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_tasks_digit_routes_through_resolver(
    mock_review: object,
    mock_save: object,
) -> None:
    """review_tasks with a digit input resolves paths via CF."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    with _patch_client():
        runner.invoke(app, ["review", "tasks", "118"])
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    assert call_args[0][0] == "tasks"  # template name
    inputs = call_args[0][1]
    assert "118-tasks.composed-workflows.md" in inputs["input"]
    assert "118-slice.composed-workflows.md" in inputs["against"]


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_slice_digit_routes_through_resolver(
    mock_review: object,
    mock_save: object,
) -> None:
    """review_slice with a digit input resolves paths via CF."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    with _patch_client():
        runner.invoke(app, ["review", "slice", "118"])
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    assert call_args[0][0] == "slice"
    inputs = call_args[0][1]
    assert "118-slice.composed-workflows.md" in inputs["input"]
    assert "100-arch.orchestration-v2.md" in inputs["against"]


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_arch_alias_delegates_to_slice(
    mock_review: object,
    mock_save: object,
) -> None:
    """review arch hidden alias delegates to review_slice and prints deprecation."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    with _patch_client():
        result = runner.invoke(app, ["review", "arch", "118"])
    assert "deprecated" in result.output.lower()
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    # Alias delegates to review_slice, which passes "slice" template name
    assert call_args[0][0] == "slice"
