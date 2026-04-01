"""Tests for CommitAction."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext


@pytest.fixture
def action() -> CommitAction:
    return CommitAction()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with initial commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    # Initial commit so HEAD exists
    readme = tmp_path / "README.md"
    readme.write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


def _make_context(cwd: str, **params: object) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params=dict(params),
        step_name="commit-step",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=cwd,
    )


def test_action_type(action: CommitAction) -> None:
    assert action.action_type == "commit"


def test_protocol_compliance(action: CommitAction) -> None:
    assert isinstance(action, Action)


@pytest.mark.asyncio
async def test_no_changes_returns_committed_false(
    action: CommitAction, git_repo: Path
) -> None:
    ctx = _make_context(str(git_repo))
    result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["committed"] is False


@pytest.mark.asyncio
async def test_creates_commit_when_changes_exist(
    action: CommitAction, git_repo: Path
) -> None:
    (git_repo / "new_file.txt").write_text("hello")
    ctx = _make_context(str(git_repo), message="feat: test commit")

    result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["committed"] is True
    assert result.outputs["message"] == "feat: test commit"
    assert isinstance(result.outputs["sha"], str)
    assert len(str(result.outputs["sha"])) == 40


@pytest.mark.asyncio
async def test_commit_message_from_params(action: CommitAction, git_repo: Path) -> None:
    (git_repo / "file.txt").write_text("data")
    ctx = _make_context(str(git_repo), message="docs: custom message")

    result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["message"] == "docs: custom message"


@pytest.mark.asyncio
async def test_auto_generated_message(action: CommitAction, git_repo: Path) -> None:
    (git_repo / "file.txt").write_text("data")
    ctx = _make_context(str(git_repo))

    result = await action.execute(ctx)

    assert result.success is True
    msg = str(result.outputs["message"])
    assert "commit-step" in msg
    assert "test-pipeline" in msg
    assert msg.startswith("chore:")


@pytest.mark.asyncio
async def test_paths_param_scopes_staging(action: CommitAction, git_repo: Path) -> None:
    (git_repo / "include.txt").write_text("yes")
    (git_repo / "exclude.txt").write_text("no")
    ctx = _make_context(str(git_repo), paths=["include.txt"], message="feat: scoped")

    result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["committed"] is True
    # Verify exclude.txt is still untracked
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert "exclude.txt" in status.stdout


@pytest.mark.asyncio
async def test_returns_sha_in_outputs(action: CommitAction, git_repo: Path) -> None:
    (git_repo / "file.txt").write_text("data")
    ctx = _make_context(str(git_repo), message="feat: sha test")

    result = await action.execute(ctx)

    sha = str(result.outputs["sha"])
    # Verify SHA matches actual HEAD
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert sha == head.stdout.strip()


@pytest.mark.asyncio
async def test_git_failure_returns_error(action: CommitAction, tmp_path: Path) -> None:
    # tmp_path is NOT a git repo — git status will fail
    ctx = _make_context(str(tmp_path))

    result = await action.execute(ctx)

    assert result.success is False
    assert result.error is not None
