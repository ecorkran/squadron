"""Item resume returns to the target before anything reads the tree (slice 197 D8, criterion 14)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.pipeline.batch_report import BatchItemRecord, ItemDecision, ItemOutcome, ItemRerun
from squadron.pipeline.item_resume import ResumeExit, ResumeOutcome, ResumeRequest, resume_item
from squadron.pipeline.state import StateManager
from tests.conftest import run_test_git
from tests.pipeline.item_resume_support import Project, branch, design, make_project


@pytest.fixture
def project(temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    monkeypatch.chdir(temp_git_repo)
    return make_project(temp_git_repo, tmp_path / "runs")


def _passing_body() -> AsyncMock:
    async def body(_pipeline: str, _params: dict[str, object], rerun: ItemRerun) -> None:
        rerun.replace(BatchItemRecord("401", "S401", ItemOutcome.PASSED))

    return AsyncMock(side_effect=body)


async def _resume(project: Project, body: AsyncMock) -> ResumeOutcome:
    return await resume_item(
        ResumeRequest(run_id=project.run_id, index="401", decision=ItemDecision.RETRY),
        cwd=str(project.repo),
        cf_client=project.cf,
        state_manager=StateManager(runs_dir=project.runs_dir),
        run_body=body,
    )


@pytest.mark.asyncio
async def test_a_flagged_branch_keeps_its_leftovers_and_the_resume_continues_from_the_target(
    project: Project,
) -> None:
    run_test_git(project.repo, "checkout", "-q", branch(401))
    (project.repo / "leftover.py").write_text("half done\n")
    body = _passing_body()

    outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.RESOLVED
    body.assert_awaited_once()
    assert project.current_branch() == "main"
    subjects = run_test_git(project.repo, "log", branch(401), "--format=%s").splitlines()
    assert subjects[0] == "chore: preserve uncommitted work on flagged slice 401"
    assert "leftover.py" in run_test_git(project.repo, "ls-tree", "-r", "--name-only", branch(401))


@pytest.mark.asyncio
async def test_the_source_reads_the_target_not_the_flagged_branch(project: Project) -> None:
    run_test_git(project.repo, "checkout", "-q", branch(401))
    seen: list[str] = []
    original = project.cf.list_slices.side_effect

    def list_slices(*args: object) -> object:
        seen.append(project.current_branch())
        return original(*args)

    project.cf.list_slices.side_effect = list_slices

    await _resume(project, _passing_body())

    assert seen and set(seen) == {"main"}


@pytest.mark.asyncio
async def test_an_unrelated_branch_is_rejected_with_nothing_changed(project: Project) -> None:
    run_test_git(project.repo, "checkout", "-q", "-b", "feature/x")
    before = run_test_git(project.repo, "for-each-ref", "--format=%(refname) %(objectname)")
    body = _passing_body()

    outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.REJECTED
    assert outcome.message.startswith("on feature/x, expected main")
    assert project.current_branch() == "feature/x"
    assert run_test_git(project.repo, "for-each-ref", "--format=%(refname) %(objectname)") == before
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_dirty_target_is_rejected(project: Project) -> None:
    (project.repo / "stray.txt").write_text("x\n")
    body = _passing_body()

    outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.REJECTED
    assert outcome.message.startswith("working tree not clean: stray.txt")
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_batch_items_interrupted_edit_on_the_target_is_committed(project: Project) -> None:
    """Issue 248: item 402's half-revised design no longer blocks retrying item 401."""
    (project.repo / design(402)).write_text("---\ndependencies: [401]\n---\nrevised\n")
    body = _passing_body()

    outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.RESOLVED
    body.assert_awaited_once()
    subject = run_test_git(project.repo, "log", "-1", "--format=%s", "main").strip()
    assert subject == "chore: preserve interrupted work on batch items"
    assert run_test_git(project.repo, "status", "--porcelain").strip() == ""


@pytest.mark.asyncio
async def test_a_stray_path_beside_an_item_edit_still_rejects_with_nothing_committed(
    project: Project,
) -> None:
    (project.repo / design(402)).write_text("revised\n")
    (project.repo / "stray.txt").write_text("x\n")
    head = run_test_git(project.repo, "rev-parse", "main").strip()
    body = _passing_body()

    outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.REJECTED
    assert outcome.message.startswith("working tree not clean:")
    assert run_test_git(project.repo, "rev-parse", "main").strip() == head
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_restore_halts(project: Project, caplog: pytest.LogCaptureFixture) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    run_test_git(project.repo, "checkout", "-q", branch(401))
    (project.repo / "leftover.py").write_text("half done\n")

    def fake(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "commit" else real_run_git(args, cwd=cwd)

    body = _passing_body()
    with (
        patch("squadron.pipeline.branch_ops.run_git", side_effect=fake),
        caplog.at_level("ERROR"),
    ):
        outcome = await _resume(project, body)

    assert outcome.exit is ResumeExit.HALTED
    body.assert_not_awaited()
    assert any(r.levelname == "ERROR" for r in caplog.records)
