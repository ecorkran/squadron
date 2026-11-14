"""``sq run --producer-only`` on dry, fresh and resumed runs (slice 424, Task 7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import _load_run_definition
from squadron.pipeline.control_params import RUN_PRODUCER_ONLY
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from squadron.pipeline.producer_only import producer_only_definition
from squadron.pipeline.state import ProducerOnlyRecord, StateManager
from squadron.pipeline.steps import bootstrap_step_types, get_step_type
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client

runner = CliRunner()

COMMIT_SHA = "abc1234"
_REVIEW_ACTIONS = {"review", "checkpoint"}


def _text(result: Result) -> str:
    # Typer forces colour in CI, so strip styling and normalise wrapping before matching.
    return " ".join(click.unstyle(result.output).split())


def _expanded_action_names(pipeline: str) -> list[str]:
    bootstrap_step_types()
    step = producer_only_definition(load_pipeline(pipeline)).definition.steps[0]
    return [
        f"{action}:{config['operation']}" if action == "cf-op" else action
        for action, config in get_step_type(step.step_type).expand(step)
    ]


class _Harness:
    """A fake action registry the CLI's executor call is wrapped to use."""

    def __init__(self) -> None:
        self.dispatch = AsyncMock(
            return_value=ActionResult(success=True, action_type="dispatch", outputs={})
        )
        self.commit = AsyncMock(
            return_value=ActionResult(
                success=True,
                action_type="commit",
                outputs={"committed": True, "sha": COMMIT_SHA},
            )
        )
        self.cf_op = AsyncMock(return_value=ActionResult(success=True, action_type="cf-op", outputs={}))
        self.review = AsyncMock(
            return_value=ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")
        )

    def registry(self) -> dict[str, object]:
        def action(execute: AsyncMock) -> MagicMock:
            mock = MagicMock()
            mock.execute = execute
            return mock

        return {
            "cf-op": action(self.cf_op),
            "dispatch": action(self.dispatch),
            "commit": action(self.commit),
            "review": action(self.review),
            "checkpoint": action(self.cf_op),
            "branch": action(self.cf_op),
        }


@pytest.fixture
def harness() -> Iterator[_Harness]:
    fakes = _Harness()
    real_execute = execute_pipeline

    async def execute_with_fakes(*args: Any, **kwargs: Any) -> PipelineResult:
        kwargs["_action_registry"] = fakes.registry()
        return await real_execute(*args, **kwargs)

    cf_client = phase_artifact_cf_client(7, "7-slice.x.md", "7-tasks.x.md")
    with (
        patch("squadron.cli.commands.run.execute_pipeline", execute_with_fakes),
        patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
        patch("squadron.cli.commands.run._check_cf"),
    ):
        yield fakes


@pytest.fixture
def slice_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo on the branch for slice 7, as the checkout of a producer-only run."""
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "7-slice.x")
    monkeypatch.chdir(temp_git_repo)
    return temp_git_repo


@pytest.fixture
def main_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(temp_git_repo)
    return temp_git_repo


def test_dry_run_lists_only_the_producer_step(slice_repo: Path) -> None:
    with patch(
        "squadron.cli.commands.run.ContextForgeClient",
        return_value=phase_artifact_cf_client(7, "7-slice.x.md", "7-tasks.x.md"),
    ):
        result = runner.invoke(app, ["run", "P6", "7", "--producer-only", "--dry-run"])

    assert result.exit_code == 0, result.output
    output = _text(result)
    steps = output.split("Steps:")[1].split("producer-only:")[0]
    assert "implement-1" in steps
    for skipped in ("close-out", "revise-code", "devlog-4", "summary-6", "branch-0"):
        assert skipped not in steps
    assert (
        "producer-only: step implement-1; skipped: branch-0, close-out, revise-code, "
        "devlog-4, branch-5, summary-6" in output
    )


def test_the_one_step_expands_to_the_cf_ops_dispatch_and_commit_only() -> None:
    assert _expanded_action_names("P6") == [
        "cf-op:set_slice",
        "cf-op:check_decisions",
        "cf-op:set_phase",
        "cf-op:build_context",
        "dispatch",
        "commit",
    ]


def test_a_fresh_run_executes_one_step_and_prints_the_stop_line(
    slice_repo: Path, harness: _Harness
) -> None:
    result = runner.invoke(app, ["run", "P6", "7", "--producer-only", "--max-cost", "5"])

    assert result.exit_code == 0, result.output
    assert _text(result).count("producer-only: stopped after implement-1") == 1
    assert (
        f"producer-only: stopped after implement-1 (commit {COMMIT_SHA}); skipped: branch-0, "
        "close-out, revise-code, devlog-4, branch-5, summary-6" in _text(result)
    )
    harness.dispatch.assert_awaited_once()
    harness.commit.assert_awaited_once()
    harness.review.assert_not_called()

    state = StateManager().load(_only_run_id())
    assert state.producer_only == ProducerOnlyRecord(
        step="implement-1",
        skipped=["branch-0", "close-out", "revise-code", "devlog-4", "branch-5", "summary-6"],
    )
    assert state.params[RUN_PRODUCER_ONLY] is True
    assert [step.step_name for step in state.completed_steps] == ["implement-1"]


def _only_run_id() -> str:
    runs = StateManager().list_runs()
    assert len(runs) == 1
    return runs[0].run_id


def test_resume_of_a_producer_only_run_executes_only_that_step(
    slice_repo: Path, harness: _Harness
) -> None:
    manager = StateManager()
    record = ProducerOnlyRecord(step="implement-1", skipped=["branch-0"])
    run_id = manager.init_run(
        "p6",
        {"slice": "7", "model": "sonnet", RUN_PRODUCER_ONLY: True},
        producer_only=record,
    )
    manager.finalize(
        run_id,
        PipelineResult(pipeline_name="p6", status=ExecutionStatus.FAILED, step_results=[], error="x"),
    )

    result = runner.invoke(app, ["run", "--resume", run_id])

    assert result.exit_code == 0, result.output
    harness.dispatch.assert_awaited_once()
    harness.review.assert_not_called()
    state = manager.load(run_id)
    assert [step.step_name for step in state.completed_steps] == ["implement-1"]
    assert "producer-only: stopped after implement-1" in _text(result)


def test_load_run_definition_of_a_producer_only_state_returns_one_step(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p6", {"slice": "7", RUN_PRODUCER_ONLY: True})

    definition = _load_run_definition(manager.load(run_id), file=MagicMock())

    assert [step.step_type for step in definition.steps] == ["implement"]


def test_load_run_definition_of_a_plain_state_keeps_every_step(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p6", {"slice": "7"})

    definition = _load_run_definition(manager.load(run_id), file=MagicMock())

    assert len(definition.steps) == len(load_pipeline("P6").steps)


def test_a_pipeline_that_changed_shape_exits_1_on_reload(tmp_path: Path) -> None:
    from click.exceptions import Exit

    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p456", {"slice": "7", RUN_PRODUCER_ONLY: True})

    with pytest.raises(Exit) as raised:
        _load_run_definition(manager.load(run_id), file=MagicMock())

    assert raised.value.exit_code == 1


def test_multi_producer_pipeline_exits_1_naming_the_candidates(
    slice_repo: Path, harness: _Harness
) -> None:
    result = runner.invoke(app, ["run", "P456", "7", "--producer-only"])

    assert result.exit_code == 1
    output = _text(result)
    for name in ("design-0", "tasks-2", "implement-8"):
        assert name in output
    harness.dispatch.assert_not_called()


def test_off_the_slice_branch_it_refuses_before_any_dispatch(
    main_repo: Path, harness: _Harness
) -> None:
    result = runner.invoke(app, ["run", "P6", "7", "--producer-only"])

    assert result.exit_code == 1
    assert (
        "Error: --producer-only does not run branch: enter; check out the branch for slice 7 "
        "first (on main)." in _text(result)
    )
    harness.dispatch.assert_not_called()


def test_off_the_slice_branch_a_dry_run_refuses_too(main_repo: Path) -> None:
    result = runner.invoke(app, ["run", "P6", "7", "--producer-only", "--dry-run"])

    assert result.exit_code == 1
    assert "check out the branch for slice 7 first" in _text(result)


def test_on_a_different_slices_branch_it_refuses(slice_repo: Path, harness: _Harness) -> None:
    result = runner.invoke(app, ["run", "P6", "8", "--producer-only"])

    assert result.exit_code == 1
    assert "check out the branch for slice 8 first (on 7-slice.x)" in _text(result)
    harness.dispatch.assert_not_called()


def test_a_non_integer_slice_refuses_naming_it(slice_repo: Path, harness: _Harness) -> None:
    result = runner.invoke(app, ["run", "P6", "seven", "--producer-only"])

    assert result.exit_code == 1
    assert "integer slice index" in _text(result)
    assert "'seven'" in _text(result)
    harness.dispatch.assert_not_called()
