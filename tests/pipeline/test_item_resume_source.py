"""Item resume re-selects the item, reconciles a merged one, and checks its dependencies
(slice 197 D8, Task 28b; criteria 9, 17)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from squadron.integrations.context_forge import SliceEntry
from squadron.pipeline.batch_report import ItemDecision
from squadron.pipeline.item_resume import (
    RECONCILED_REASON,
    ResumeExit,
    ResumeOutcome,
    ResumeRequest,
    resume_item,
)
from squadron.pipeline.state import StateManager
from tests.conftest import run_test_git
from tests.pipeline.item_resume_support import Project, branch, make_project


@pytest.fixture
def project(temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    monkeypatch.chdir(temp_git_repo)
    return make_project(temp_git_repo, tmp_path / "runs")


async def _resume(project: Project, index: str, body: AsyncMock) -> ResumeOutcome:
    return await resume_item(
        ResumeRequest(run_id=project.run_id, index=index, decision=ItemDecision.RETRY),
        cwd=str(project.repo),
        cf_client=project.cf,
        state_manager=StateManager(runs_dir=project.runs_dir),
        run_body=body,
    )


@pytest.mark.asyncio
async def test_a_slice_merged_before_the_report_was_rewritten_reconciles(
    project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    run_test_git(project.repo, "merge", "-q", "--no-ff", "-m", "merge: slice 401 — S401", branch(401))
    project.status[401] = "complete"
    body = AsyncMock()

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.item_resume"):
        outcome = await _resume(project, "401", body)

    assert outcome.exit is ResumeExit.RESOLVED
    body.assert_not_awaited()
    record = project.record("401")
    assert (record.outcome, record.reason, record.decision) == ("passed", RECONCILED_REASON, "retry")
    assert any(RECONCILED_REASON in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_a_deferred_slice_is_rejected_naming_its_status(project: Project) -> None:
    project.status[401] = "deferred"
    body = AsyncMock()

    outcome = await _resume(project, "401", body)

    assert outcome.exit is ResumeExit.REJECTED
    assert "item 401 is no longer selected" in outcome.message
    assert outcome.message.endswith("status deferred")
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_undesigned_slice_is_rejected(project: Project) -> None:
    original = project.cf.list_slices.side_effect

    def without_401_design(*args: object) -> list[SliceEntry]:
        return [
            SliceEntry(e.index, e.name, None, e.status) if e.index == 401 else e
            for e in original(*args)
        ]

    project.cf.list_slices.side_effect = without_401_design
    body = AsyncMock()

    outcome = await _resume(project, "401", body)

    assert outcome.exit is ResumeExit.REJECTED
    assert outcome.message.endswith("status not_started")
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_without_a_merged_branch_is_rejected(project: Project) -> None:
    project.status[401] = "complete"
    body = AsyncMock()

    outcome = await _resume(project, "401", body)

    assert outcome.exit is ResumeExit.REJECTED
    assert outcome.message.endswith(f"status complete but {branch(401)} is not merged into main")
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_dependency_still_open_on_the_target_flags_without_running(
    project: Project,
) -> None:
    body = AsyncMock()

    outcome = await _resume(project, "402", body)

    assert outcome.exit is ResumeExit.FLAGGED
    body.assert_not_awaited()
    record = project.record("402")
    assert (record.outcome, record.flag_kind, record.reason, record.decision) == (
        "flagged",
        "dependency",
        "dependency 401 not complete",
        "retry",
    )


@pytest.mark.asyncio
async def test_resume_hands_the_source_the_run_cwd(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    from squadron.pipeline import item_resume

    real = item_resume.evaluate_each_source
    seen: list[str] = []

    async def recording(*args: object, cwd: str, **kwargs: object):  # type: ignore[no-untyped-def]
        seen.append(cwd)
        return await real(*args, cwd=cwd, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(item_resume, "evaluate_each_source", recording)
    await _resume(project, "401", AsyncMock())
    assert seen == [str(project.repo)]


@pytest.mark.asyncio
async def test_a_dependency_merged_in_git_does_not_block_while_cf_still_reports_it_open(
    project: Project,
) -> None:
    run_test_git(project.repo, "merge", "-q", "--no-ff", "-m", "merge: slice 401 — S401", branch(401))
    assert project.status[401] == "not_started"
    body = AsyncMock()

    outcome = await _resume(project, "402", body)

    body.assert_awaited_once()
    assert "not complete" not in outcome.message


@pytest.mark.asyncio
async def test_a_merged_slice_reconciles_to_passed_whatever_cf_reports(project: Project) -> None:
    run_test_git(project.repo, "merge", "-q", "--no-ff", "-m", "merge: slice 401 — S401", branch(401))
    assert project.status[401] == "not_started"
    body = AsyncMock()

    outcome = await _resume(project, "401", body)

    assert outcome.exit is ResumeExit.RESOLVED
    body.assert_not_awaited()
    assert project.record("401").reason == RECONCILED_REASON


@pytest.mark.asyncio
async def test_a_predicate_failure_halts_and_leaves_the_report_unchanged(
    project: Project, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from squadron.pipeline import item_resume
    from squadron.pipeline.git_ops import GitStateUnknownError

    def failing(*_: object, **__: object) -> set[int]:
        raise GitStateUnknownError("cannot read the history of main (git rev-list): boom")

    monkeypatch.setattr(item_resume, "merged_slice_branches", failing)
    before = project.report_path.read_bytes()

    with caplog.at_level(logging.ERROR, logger="squadron.pipeline.item_resume"):
        outcome = await _resume(project, "402", AsyncMock())

    assert outcome.exit is ResumeExit.HALTED
    assert "cannot read the history of main" in outcome.message
    assert project.report_path.read_bytes() == before
    assert any(r.levelno == logging.ERROR for r in caplog.records)
