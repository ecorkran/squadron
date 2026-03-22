"""Tests for CLI slice number resolution in review commands."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import click.exceptions
import pytest

from squadron.cli.commands.review import _resolve_slice_number

# ---------------------------------------------------------------------------
# Sample CF output fixtures
# ---------------------------------------------------------------------------

SLICE_LIST_JSON = json.dumps(
    {
        "slicePlan": "100-slices.orchestration-v2",
        "total": 2,
        "completed": 1,
        "entries": [
            {
                "index": 118,
                "name": "Claude Code Commands — Composed Workflows",
                "isChecked": True,
                "designFile": (
                    "project-documents/user/slices/118-slice.composed-workflows.md"
                ),
                "isActive": True,
                "isNext": False,
            },
            {
                "index": 119,
                "name": "Conversation Persistence",
                "isChecked": False,
                "designFile": None,
                "isActive": False,
                "isNext": True,
            },
        ],
    }
)

TASKS_LIST_JSON = json.dumps(
    [
        {
            "index": 118,
            "name": "Claude Code Commands — Composed Workflows",
            "files": ["118-tasks.composed-workflows.md"],
            "completed": 10,
            "total": 20,
            "isActive": True,
        },
    ]
)

GET_JSON = json.dumps(
    {
        "name": "squadron",
        "fileArch": "100-arch.orchestration-v2",
        "fileSlicePlan": "100-slices.orchestration-v2",
        "projectPath": "/fake/path",
    }
)


def _mock_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
    """Return canned CF output based on command args."""
    cmd = " ".join(str(a) for a in args)
    if "slice list --json" in cmd:
        return subprocess.CompletedProcess(args, 0, stdout=SLICE_LIST_JSON, stderr="")
    if "tasks list --json" in cmd:
        return subprocess.CompletedProcess(args, 0, stdout=TASKS_LIST_JSON, stderr="")
    if "get --json" in cmd:
        return subprocess.CompletedProcess(args, 0, stdout=GET_JSON, stderr="")
    raise ValueError(f"Unexpected cf command: {cmd}")


# ---------------------------------------------------------------------------
# _resolve_slice_number tests
# ---------------------------------------------------------------------------


@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
def test_resolve_valid_slice(mock_run: object) -> None:
    """Resolves a known slice number to correct paths."""
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


@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
def test_resolve_slice_no_design_file(mock_run: object) -> None:
    """Resolves a slice with null designFile — slice_name derived from entry name."""
    info = _resolve_slice_number("119")
    assert info["index"] == 119
    assert info["design_file"] is None
    assert info["slice_name"] == "conversation-persistence"


@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
def test_resolve_slice_not_found(mock_run: object) -> None:
    """Exits with error when slice number doesn't exist."""
    with pytest.raises((SystemExit, click.exceptions.Exit)):
        _resolve_slice_number("999")


@patch(
    "squadron.cli.commands.review.subprocess.run",
    side_effect=FileNotFoundError("cf not found"),
)
def test_resolve_slice_cf_not_installed(mock_run: object) -> None:
    """Exits with error when cf CLI is not available."""
    with pytest.raises((SystemExit, click.exceptions.Exit)):
        _resolve_slice_number("118")


# ---------------------------------------------------------------------------
# Command integration (verify digit detection routes through resolver)
# ---------------------------------------------------------------------------


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
@patch("squadron.cli.commands.review._run_review_command")
def test_review_tasks_digit_routes_through_resolver(
    mock_review: object,
    mock_run: object,
    mock_save: object,
) -> None:
    """review_tasks with a digit input resolves paths via CF."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    runner.invoke(app, ["review", "tasks", "118"])
    # Should attempt to run review (may fail at API call, but resolver ran)
    # If _run_review_command was called, it means resolution succeeded
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    assert call_args[0][0] == "tasks"  # template name
    inputs = call_args[0][1]
    assert "118-tasks.composed-workflows.md" in inputs["input"]
    assert "118-slice.composed-workflows.md" in inputs["against"]


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
@patch("squadron.cli.commands.review._run_review_command")
def test_review_slice_digit_routes_through_resolver(
    mock_review: object,
    mock_run: object,
    mock_save: object,
) -> None:
    """review_slice with a digit input resolves paths via CF."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    runner.invoke(app, ["review", "slice", "118"])
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    assert call_args[0][0] == "slice"
    inputs = call_args[0][1]
    assert "118-slice.composed-workflows.md" in inputs["input"]
    assert "100-arch.orchestration-v2.md" in inputs["against"]


@patch("squadron.cli.commands.review._save_review_file")
@patch("squadron.cli.commands.review.subprocess.run", side_effect=_mock_run)
@patch("squadron.cli.commands.review._run_review_command")
def test_review_arch_alias_delegates_to_slice(
    mock_review: object,
    mock_run: object,
    mock_save: object,
) -> None:
    """review arch hidden alias delegates to review_slice and prints deprecation."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    result = runner.invoke(app, ["review", "arch", "118"])
    assert "deprecated" in result.output.lower()
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    # Alias delegates to review_slice, which passes "slice" template name
    assert call_args[0][0] == "slice"
