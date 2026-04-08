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


@patch("squadron.cli.commands.review.save_review_result")
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


@patch("squadron.cli.commands.review.save_review_result")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_tasks_split_files_reviews_each_part(
    mock_review: object,
    mock_save: object,
) -> None:
    """Split task files are reviewed independently, each with a part-N suffix."""
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from squadron.cli.app import app
    from squadron.review.models import Verdict

    # All parts pass so the command exit code is 0.
    mock_review.return_value = MagicMock(verdict=Verdict.PASS)  # type: ignore[attr-defined]

    split_entries = [
        TaskEntry(
            index=161,
            files=[
                "161-tasks.summary-step-with-emit-destinations-1.md",
                "161-tasks.summary-step-with-emit-destinations-2.md",
            ],
        ),
    ]
    split_slices = [
        SliceEntry(
            index=161,
            name="Summary Step with Emit Destinations",
            design_file=(
                "project-documents/user/slices/"
                "161-slice.summary-step-with-emit-destinations.md"
            ),
            status="not_started",
        ),
    ]

    runner = CliRunner()
    with patch(
        "squadron.cli.commands.review.ContextForgeClient",
        **{
            "return_value.list_slices.return_value": split_slices,
            "return_value.list_tasks.return_value": split_entries,
            "return_value.get_project.return_value": PROJECT_INFO,
        },
    ):
        result = runner.invoke(app, ["review", "tasks", "161"])

    assert result.exit_code == 0
    # _run_review_command is called once per part.
    assert mock_review.call_count == 2  # type: ignore[union-attr]
    # First call: part 1's path.
    first_inputs = mock_review.call_args_list[0][0][1]  # type: ignore[union-attr]
    assert "161-tasks.summary-step-with-emit-destinations-1.md" in first_inputs["input"]
    # Second call: part 2's path.
    second_inputs = mock_review.call_args_list[1][0][1]  # type: ignore[union-attr]
    assert (
        "161-tasks.summary-step-with-emit-destinations-2.md" in second_inputs["input"]
    )
    # Both saves carry a part-N suffix.
    assert mock_save.call_count == 2  # type: ignore[union-attr]
    first_save_kwargs = mock_save.call_args_list[0][1]  # type: ignore[union-attr]
    second_save_kwargs = mock_save.call_args_list[1][1]  # type: ignore[union-attr]
    assert first_save_kwargs["name_suffix"] == "part-1"
    assert second_save_kwargs["name_suffix"] == "part-2"


@patch("squadron.cli.commands.review.save_review_result")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_tasks_single_file_no_suffix(
    mock_review: object,
    mock_save: object,
) -> None:
    """Single task file review still saves without a part suffix (regression)."""
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from squadron.cli.app import app
    from squadron.review.models import Verdict

    mock_review.return_value = MagicMock(verdict=Verdict.PASS)  # type: ignore[attr-defined]

    runner = CliRunner()
    with _patch_client():
        result = runner.invoke(app, ["review", "tasks", "118"])

    assert result.exit_code == 0
    assert mock_save.call_count == 1  # type: ignore[union-attr]
    save_kwargs = mock_save.call_args_list[0][1]  # type: ignore[union-attr]
    assert save_kwargs["name_suffix"] is None


@patch("squadron.cli.commands.review.save_review_result")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_tasks_split_files_aggregates_verdict(
    mock_review: object,
    mock_save: object,
) -> None:
    """If any part FAILs, the overall exit code is 2."""
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from squadron.cli.app import app
    from squadron.review.models import Verdict

    # Part 1 passes, part 2 fails → overall FAIL → exit 2.
    mock_review.side_effect = [  # type: ignore[attr-defined]
        MagicMock(verdict=Verdict.PASS),
        MagicMock(verdict=Verdict.FAIL),
    ]

    split_entries = [
        TaskEntry(
            index=161,
            files=[
                "161-tasks.summary-step-with-emit-destinations-1.md",
                "161-tasks.summary-step-with-emit-destinations-2.md",
            ],
        ),
    ]
    split_slices = [
        SliceEntry(
            index=161,
            name="Summary Step with Emit Destinations",
            design_file=(
                "project-documents/user/slices/"
                "161-slice.summary-step-with-emit-destinations.md"
            ),
            status="not_started",
        ),
    ]

    runner = CliRunner()
    with patch(
        "squadron.cli.commands.review.ContextForgeClient",
        **{
            "return_value.list_slices.return_value": split_slices,
            "return_value.list_tasks.return_value": split_entries,
            "return_value.get_project.return_value": PROJECT_INFO,
        },
    ):
        result = runner.invoke(app, ["review", "tasks", "161"])

    assert result.exit_code == 2
    # Both parts were still reviewed and saved despite the failure.
    assert mock_review.call_count == 2  # type: ignore[union-attr]
    assert mock_save.call_count == 2  # type: ignore[union-attr]


def test_aggregate_verdicts_ordering() -> None:
    """_aggregate_verdicts returns the worst verdict (FAIL > CONCERNS > PASS)."""
    from unittest.mock import MagicMock

    from squadron.cli.commands.review import _aggregate_verdicts
    from squadron.review.models import Verdict

    assert _aggregate_verdicts([]) == Verdict.PASS
    assert _aggregate_verdicts([MagicMock(verdict=Verdict.PASS)]) == Verdict.PASS
    assert (
        _aggregate_verdicts(
            [MagicMock(verdict=Verdict.PASS), MagicMock(verdict=Verdict.CONCERNS)]
        )
        == Verdict.CONCERNS
    )
    assert (
        _aggregate_verdicts(
            [
                MagicMock(verdict=Verdict.CONCERNS),
                MagicMock(verdict=Verdict.FAIL),
                MagicMock(verdict=Verdict.PASS),
            ]
        )
        == Verdict.FAIL
    )


@patch("squadron.cli.commands.review.save_review_result")
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


@patch("squadron.cli.commands.review.save_review_result")
@patch("squadron.cli.commands.review._run_review_command")
def test_review_arch_resolves_index(
    mock_review: object,
    mock_save: object,
    tmp_path: object,
) -> None:
    """review arch resolves an initiative index to an architecture document."""
    from typer.testing import CliRunner

    from squadron.cli.app import app

    runner = CliRunner()
    # When no matching arch file exists, it should error clearly
    result = runner.invoke(app, ["review", "arch", "999"])
    assert result.exit_code == 1
    assert "no architecture document" in result.output.lower()

    # When a matching file exists, it should use the "arch" template
    result = runner.invoke(
        app,
        [
            "review",
            "arch",
            "project-documents/user/architecture/140-arch.pipeline-foundation.md",
            "--no-save",
        ],
    )
    assert mock_review.called  # type: ignore[union-attr]
    call_args = mock_review.call_args  # type: ignore[union-attr]
    assert call_args[0][0] == "arch"
