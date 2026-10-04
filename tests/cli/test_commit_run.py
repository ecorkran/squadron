"""Tests for the hidden ``sq _commit`` command (slice 196 Task 18)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.models import ActionContext
from tests.conftest import run_test_git

runner = CliRunner()

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.batch-foo.md"


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=DESIGN_FILE, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.batch-foo.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file="project-documents/user/architecture/100-arch.plan-name.md",
        slice_plan="100-slices.plan-name",
        phase="Phase 4",
        slice=str(SLICE),
        name="squadron",
    )
    client.get_config.return_value = ""
    return client


def _write(repo: Path, relative: str, text: str = "content\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def in_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """The cwd is the temp repo and the CLI's cf client is the fake."""
    monkeypatch.chdir(temp_git_repo)
    with patch("squadron.cli.commands.commit_run.ContextForgeClient", return_value=_cf()):
        yield temp_git_repo


def test_commits_and_prints_the_sha_and_message(in_repo: Path) -> None:
    _write(in_repo, DESIGN_FILE)
    _write(in_repo, DESIGN_REVIEW, "---\nverdict: CONCERNS\n---\n")

    result = runner.invoke(
        app, ["_commit", "--subject", "design", "--slice", "105", "--template", "slice"]
    )

    assert result.exit_code == 0, result.output
    sha = run_test_git(in_repo, "rev-parse", "HEAD").strip()
    assert result.output.strip() == f"committed {sha} docs: add slice 105 design (review: CONCERNS)"


def test_nothing_to_commit_exits_zero(in_repo: Path) -> None:
    result = runner.invoke(app, ["_commit", "--subject", "design", "--slice", "105"])

    assert result.exit_code == 0
    assert "nothing to commit" in result.output


def test_misplaced_planning_commit_exits_one_with_the_actions_text(in_repo: Path) -> None:
    run_test_git(in_repo, "checkout", "-q", "-b", "scratch")
    _write(in_repo, DESIGN_FILE)

    result = runner.invoke(app, ["_commit", "--subject", "design", "--slice", "105"])

    assert result.exit_code == 1
    assert "planning commit for slice 105 on scratch; expected main" in result.output


def test_code_off_its_slice_branch_exits_one(in_repo: Path) -> None:
    _write(in_repo, "src/feature.py")

    result = runner.invoke(app, ["_commit", "--subject", "code", "--slice", "105"])

    assert result.exit_code == 1
    assert "refusing to stage all changes off the slice branch (on main)" in result.output


def test_explicit_paths_commit_only_those_paths_verbatim(in_repo: Path) -> None:
    _write(in_repo, "notes/a.md")
    _write(in_repo, "notes/stray.md")

    result = runner.invoke(app, ["_commit", "--path", "notes/a.md", "--message", "docs: add a"])

    assert result.exit_code == 0, result.output
    assert run_test_git(in_repo, "log", "-1", "--format=%s").strip() == "docs: add a"
    committed = run_test_git(in_repo, "show", "--name-only", "--format=", "HEAD").split()
    assert committed == ["notes/a.md"]


def test_no_subject_and_no_paths_exits_one_with_the_actions_refusal(in_repo: Path) -> None:
    result = runner.invoke(app, ["_commit"])

    assert result.exit_code == 1
    assert "refusing to stage everything" in result.output


def test_cli_and_action_give_identical_message_and_effect(
    temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interface parity: the same input commits the same paths with the same message."""
    import asyncio

    def seed(repo: Path) -> None:
        _write(repo, DESIGN_FILE)
        _write(repo, DESIGN_REVIEW, "---\nverdict: PASS\n---\n")
        _write(repo, "stray.txt")

    seed(temp_git_repo)
    monkeypatch.chdir(temp_git_repo)
    with patch("squadron.cli.commands.commit_run.ContextForgeClient", return_value=_cf()):
        cli_result = runner.invoke(
            app, ["_commit", "--subject", "design", "--slice", "105", "--template", "slice"]
        )
    cli_message = run_test_git(temp_git_repo, "log", "-1", "--format=%s").strip()
    cli_files = run_test_git(temp_git_repo, "show", "--name-only", "--format=", "HEAD").split()
    cli_dirty = run_test_git(temp_git_repo, "status", "--porcelain")
    assert cli_result.exit_code == 0

    run_test_git(temp_git_repo, "reset", "-q", "--hard", "HEAD~1")
    (temp_git_repo / "stray.txt").unlink(missing_ok=True)
    seed(temp_git_repo)
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={
            "commit_subject": "design",
            "slice": "105",
            "review_template": "slice",
        },
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(temp_git_repo),
    )
    asyncio.run(CommitAction().execute(context))

    assert run_test_git(temp_git_repo, "log", "-1", "--format=%s").strip() == cli_message
    assert run_test_git(temp_git_repo, "show", "--name-only", "--format=", "HEAD").split() == cli_files
    assert run_test_git(temp_git_repo, "status", "--porcelain") == cli_dirty
