"""Tests for the hidden ``sq _branch`` command (slice 196 Task 26)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.models import ActionContext
from tests.conftest import run_test_git

runner = CliRunner()

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
BRANCH = "105-slice.batch-foo"


def _cf(design_file: str | None = DESIGN_FILE) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=design_file, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=[])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice=str(SLICE), name="squadron"
    )
    client.get_config.return_value = ""
    client.list_worktrees.return_value = []
    return client


@pytest.fixture
def in_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(temp_git_repo)
    with patch("squadron.cli.commands.branch_run.ContextForgeClient", return_value=_cf()):
        yield temp_git_repo


def _branch(repo: Path) -> str:
    return run_test_git(repo, "branch", "--show-current").strip()


def test_enter_creates_the_branch_and_says_so(in_repo: Path) -> None:
    result = runner.invoke(app, ["_branch", "enter", "--slice", "105"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"on {BRANCH} (created from main)"
    assert _branch(in_repo) == BRANCH


def test_enter_again_reports_the_existing_branch(in_repo: Path) -> None:
    runner.invoke(app, ["_branch", "enter", "--slice", "105"])

    result = runner.invoke(app, ["_branch", "enter", "--slice", "105"])

    assert result.output.strip() == f"on {BRANCH} (existing)"


def test_merge_reports_the_merge_and_ends_on_the_target(in_repo: Path) -> None:
    runner.invoke(app, ["_branch", "enter", "--slice", "105"])
    (in_repo / "feature.py").write_text("x\n")
    run_test_git(in_repo, "add", "-A")
    run_test_git(in_repo, "commit", "-q", "-m", "work")

    result = runner.invoke(app, ["_branch", "merge", "--slice", "105"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"merged {BRANCH} into main"
    assert _branch(in_repo) == "main"


def test_environment_fault_exits_one_with_the_actions_text(in_repo: Path) -> None:
    run_test_git(in_repo, "checkout", "-q", "-b", "scratch")

    result = runner.invoke(app, ["_branch", "enter", "--slice", "105"])

    assert result.exit_code == 1
    assert f"on scratch, expected main or {BRANCH}" in result.output


def test_item_failure_exits_one_with_the_actions_error(
    temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(temp_git_repo)
    with patch(
        "squadron.cli.commands.branch_run.ContextForgeClient",
        return_value=_cf(design_file=None),
    ):
        result = runner.invoke(app, ["_branch", "enter", "--slice", "105"])

    assert result.exit_code == 1
    assert "slice 105 has no design file" in result.output


def test_bad_op_is_rejected_by_the_cli() -> None:
    result = runner.invoke(app, ["_branch", "rebase", "--slice", "105"])
    assert result.exit_code != 0


def test_cli_and_action_end_in_the_same_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interface parity: the same enter leaves the same branch and result either way."""

    def make_repo(name: str) -> Path:
        repo = tmp_path_factory.mktemp(name)
        run_test_git(repo, "init", "-q", "-b", "main")
        (repo / "README.md").write_text("init\n")
        run_test_git(repo, "add", "-A")
        run_test_git(repo, "commit", "-q", "-m", "init")
        return repo

    cli_repo, action_repo = make_repo("cli"), make_repo("action")

    monkeypatch.chdir(cli_repo)
    with patch("squadron.cli.commands.branch_run.ContextForgeClient", return_value=_cf()):
        cli_result = runner.invoke(app, ["_branch", "enter", "--slice", "105"])
    assert cli_result.exit_code == 0

    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "enter", "slice": "105"},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(action_repo),
    )
    action_result = asyncio.run(BranchAction().execute(context))

    assert action_result.outputs == {"branch": BRANCH, "target": "main", "created": True}
    assert _branch(cli_repo) == _branch(action_repo) == BRANCH
    assert cli_result.output.strip() == f"on {BRANCH} (created from main)"
