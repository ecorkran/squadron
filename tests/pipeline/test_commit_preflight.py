"""A planning commit off the target fails the run at its start, before any step spends (#277)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.protocol import RunPreflight
from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from tests.conftest import run_test_git

SLICE_BRANCH = "101-slice.hosted-chat-loop"


def _cf(target: str = "") -> MagicMock:
    """A cf client whose ``git.integration_branch`` is *target* (empty means main)."""
    client = MagicMock()
    client.get_config.return_value = target
    return client


def _on(repo: Path, branch: str) -> str:
    run_test_git(repo, "checkout", "-q", "-b", branch)
    return str(repo)


def _tasks_commit() -> dict[str, object]:
    return {"commit_subject": "tasks", "slice": 102}


def test_commit_action_is_a_run_preflight() -> None:
    assert isinstance(CommitAction(), RunPreflight)


def test_a_planning_commit_on_the_target_passes(temp_git_repo: Path) -> None:
    CommitAction().preflight(_tasks_commit(), str(temp_git_repo), _cf())


@pytest.mark.parametrize("subject", ["design", "tasks", "architecture"])
def test_a_planning_commit_off_the_target_is_refused_with_the_runtime_message(
    temp_git_repo: Path, subject: str
) -> None:
    cwd = _on(temp_git_repo, SLICE_BRANCH)

    with pytest.raises(
        ValueError, match=f"planning commit for slice 102 on {SLICE_BRANCH}; expected main"
    ):
        CommitAction().preflight({"commit_subject": subject, "slice": 102}, cwd, _cf())


def test_an_integration_branch_is_the_target(temp_git_repo: Path) -> None:
    with pytest.raises(ValueError, match="on main; expected dev/erik"):
        CommitAction().preflight(_tasks_commit(), str(temp_git_repo), _cf("dev/erik"))


@pytest.mark.parametrize("subject", ["code", "devlog"])
def test_code_and_devlog_commits_are_left_to_the_slice_branch(
    temp_git_repo: Path, subject: str
) -> None:
    cwd = _on(temp_git_repo, SLICE_BRANCH)

    CommitAction().preflight({"commit_subject": subject, "slice": 101}, cwd, _cf())


def test_a_commit_naming_no_subject_is_not_checked(temp_git_repo: Path) -> None:
    cwd = _on(temp_git_repo, SLICE_BRANCH)

    CommitAction().preflight({"paths": ["a.md"]}, cwd, _cf())


async def test_a_fresh_run_off_the_target_stops_before_its_first_step(temp_git_repo: Path) -> None:
    cwd = _on(temp_git_repo, SLICE_BRANCH)
    definition = PipelineDefinition(
        name="p",
        description="",
        params={},
        steps=[StepConfig(step_type="tasks", name="tasks-0", config={"phase": 5, "slice": 102})],
    )
    observer = MagicMock()

    with pytest.raises(ValueError, match="planning commit for slice 102"):
        await execute_pipeline(
            definition,
            {"_project": "p"},
            resolver=MagicMock(),
            cf_client=_cf(),
            cwd=cwd,
            observer=observer,
        )

    observer.step_started.assert_not_called()
