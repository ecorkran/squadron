"""``sq review --max`` option validation and wiring through the CLI (slice 941 D6)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.review.templates import BuiltinReviewTemplate

runner = CliRunner()

_RUNNER = "squadron.cli.commands.review.run_review_revise"
_REVISE = "squadron.cli.commands.review_revise"


def _passing_result() -> PipelineResult:
    review = MagicMock(
        action_type="review",
        verdict="PASS",
        findings=[],
        outputs={"review_file": "r.md"},
        success=True,
        error=None,
    )
    steps = [
        StepResult("review", "review", ExecutionStatus.COMPLETED, [review]),
        StepResult("loop-1", "loop", ExecutionStatus.COMPLETED, [], iteration=0),
    ]
    return PipelineResult("review-revise-slice", ExecutionStatus.COMPLETED, steps)


@pytest.fixture
def execute() -> Iterator[AsyncMock]:
    """The pipeline executor, stubbed: a refusal must leave it unawaited.

    The branch checks read this checkout's git state, so they are stubbed to pass here;
    the tests of those checks patch their own inputs.
    """
    stub = AsyncMock(return_value=_passing_result())
    classification = MagicMock(needs_persistent_session=False)
    with (
        patch(f"{_REVISE}.execute_pipeline", stub),
        patch(f"{_REVISE}.classify_for_run", return_value=classification),
        patch(f"{_REVISE}.ContextForgeClient"),
    ):
        yield stub


def _invoke(*args: str) -> Any:
    return runner.invoke(app, ["review", *args])


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("slice", BuiltinReviewTemplate.SLICE),
        ("tasks", BuiltinReviewTemplate.TASKS),
        ("code", BuiltinReviewTemplate.CODE),
    ],
)
@pytest.mark.parametrize("max_args", [["--max", "3"], ["--max=3"]])
def test_each_command_routes_to_the_runner_with_its_kind(
    command: str, kind: BuiltinReviewTemplate, max_args: list[str]
) -> None:
    with (
        patch(_RUNNER, return_value=0) as run,
        patch(f"{_REVISE}._require_branch_preconditions"),
    ):
        result = _invoke(command, "941", *max_args, "--model", "sol")

    assert result.exit_code == 0, result.output
    args = run.call_args.args
    assert (args[0], args[1], args[2], args[3], args[4]) == (kind, "941", "sol", None, 3)


def test_runner_exit_code_becomes_the_commands_exit_code() -> None:
    with patch(_RUNNER, return_value=2), patch(f"{_REVISE}._require_branch_preconditions"):
        result = _invoke("slice", "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 2


def test_valid_invocation_reaches_the_executor(execute: AsyncMock) -> None:
    with patch(f"{_REVISE}._require_branch_preconditions"):
        result = _invoke("slice", "941", "--max", "2", "--model", "sol", "--revise-model", "sonnet")

    assert result.exit_code == 0, result.output
    params = execute.await_args.args[1]
    assert (params["slice"], params["review-model"], params["max-revisions"]) == ("941", "sol", "2")
    assert params["model"] == "sonnet"
    assert "final: PASS after 0 rounds" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["slice", "docs/design.md", "--against", "arch.md", "--max", "1"],
            "--max requires a slice index",
        ),
        (["tasks", "docs/tasks.md", "--max", "1"], "--max requires a slice index"),
        (["slice", "941", "--max", "1", "--json"], "--json is not supported with --max"),
        (["tasks", "941", "--max", "1", "--no-save"], "--no-save is not supported with --max"),
        (["slice", "941", "--revise-model", "opus"], "--revise-model requires --max"),
    ],
)
def test_refusals_exit_one_and_never_call_the_executor(
    args: list[str], message: str, execute: AsyncMock
) -> None:
    result = _invoke(*args)

    assert result.exit_code == 1
    assert message in result.output
    execute.assert_not_awaited()


@pytest.mark.parametrize("command", ["slice", "tasks"])
def test_planning_kinds_off_the_target_branch_name_the_target(command: str, execute: AsyncMock) -> None:
    with (
        patch(f"{_REVISE}.read_integration_target", return_value="main"),
        patch(f"{_REVISE}.current_branch", return_value="941-slice.review-loop"),
    ):
        result = _invoke(command, "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 1
    assert "must run on branch main" in result.output
    assert "941-slice.review-loop" in result.output
    execute.assert_not_awaited()


def test_planning_kind_on_the_target_branch_runs(execute: AsyncMock) -> None:
    with (
        patch(f"{_REVISE}.read_integration_target", return_value="dev/erik"),
        patch(f"{_REVISE}.current_branch", return_value="dev/erik"),
    ):
        result = _invoke("slice", "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 0, result.output
    execute.assert_awaited_once()


def test_a_git_fault_during_the_run_exits_one_with_its_message(execute: AsyncMock) -> None:
    execute.side_effect = GitEnvironmentError("planning commit for slice 941 on x; expected main")
    with patch(f"{_REVISE}._require_branch_preconditions"):
        result = _invoke("slice", "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 1
    assert "expected main" in result.output
    assert "Traceback" not in result.output


def test_code_on_the_wrong_branch_names_the_expected_branch(execute: AsyncMock) -> None:
    with (
        patch(f"{_REVISE}.slice_facts", return_value=("941-slice.review-loop", "review-loop")),
        patch(f"{_REVISE}.current_branch", return_value="main"),
    ):
        result = _invoke("code", "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 1
    assert "941-slice.review-loop" in result.output
    execute.assert_not_awaited()


def test_code_with_a_dirty_tree_lists_the_paths(execute: AsyncMock) -> None:
    with (
        patch(f"{_REVISE}.slice_facts", return_value=("941-slice.review-loop", "review-loop")),
        patch(f"{_REVISE}.current_branch", return_value="941-slice.review-loop"),
        patch(f"{_REVISE}.dirty_paths", return_value="a.py, b.py"),
    ):
        result = _invoke("code", "941", "--max", "1", "--model", "sol")

    assert result.exit_code == 1
    assert "a.py, b.py" in result.output
    execute.assert_not_awaited()


def test_arch_has_no_max_option() -> None:
    result = _invoke("arch", "941", "--max", "1")

    assert result.exit_code == 2
    assert "No such option" in result.output


@pytest.mark.parametrize("command", ["slice", "tasks", "code"])
def test_max_below_one_is_rejected_before_any_review(command: str, execute: AsyncMock) -> None:
    result = _invoke(command, "941", "--max", "0", "--model", "sol")

    assert result.exit_code == 2
    assert "--max" in result.output
    execute.assert_not_awaited()
