"""Item resume refuses bad requests before any git or model work (slice 197 D8, Task 26)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.pipeline.batch_report import ItemDecision
from squadron.pipeline.item_resume import ResumeExit, ResumeRequest, resume_item
from squadron.pipeline.run_lock import project_run_lock
from squadron.pipeline.state import StateManager
from tests.conftest import run_test_git
from tests.pipeline.item_resume_support import Project, make_project


def test_exit_codes_are_the_d8_table() -> None:
    assert [(e.name, e.value) for e in ResumeExit] == [
        ("RESOLVED", 0),
        ("FLAGGED", 1),
        ("REJECTED", 2),
        ("HALTED", 3),
    ]


@pytest.fixture
def project(temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    monkeypatch.chdir(temp_git_repo)
    return make_project(temp_git_repo, tmp_path / "runs")


def _snapshot(project: Project) -> tuple[str, str, str]:
    return (
        project.current_branch(),
        run_test_git(project.repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        project.report_path.read_text(),
    )


async def _resume(
    project: Project, request: ResumeRequest, run_body: AsyncMock | None = None
) -> tuple[object, AsyncMock]:
    body = run_body or AsyncMock()
    outcome = await resume_item(
        request,
        cwd=str(project.repo),
        cf_client=project.cf,
        state_manager=StateManager(runs_dir=project.runs_dir),
        run_body=body,
    )
    return outcome, body


def _req(project: Project, index: str, decision: ItemDecision = ItemDecision.RETRY) -> ResumeRequest:
    return ResumeRequest(run_id=project.run_id, index=index, decision=decision)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("index", "decision", "message"),
    [
        ("999", ItemDecision.RETRY, "no record for item 999 in "),
        ("403", ItemDecision.RETRY, "item 403 is passed; only flagged or not_run items resume"),
        (
            "402",
            ItemDecision.ACCEPT,
            "accept requires flagKind review_unresolved; item 402 is dependency",
        ),
        ("404", ItemDecision.ACCEPT, "accept requires flagKind review_unresolved; item 404 is not_run"),
    ],
)
async def test_a_refused_record_touches_nothing(
    project: Project, index: str, decision: ItemDecision, message: str
) -> None:
    before = _snapshot(project)

    outcome, body = await _resume(project, _req(project, index, decision))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    assert message in outcome.message  # type: ignore[attr-defined]
    body.assert_not_awaited()
    project.cf.list_slices.assert_not_called()
    assert _snapshot(project) == before


@pytest.mark.asyncio
async def test_an_unknown_run_is_rejected(project: Project) -> None:
    outcome, body = await _resume(
        project, ResumeRequest(run_id="nope", index="401", decision=ItemDecision.RETRY)
    )

    assert (outcome.exit, outcome.message) == (ResumeExit.REJECTED, "run nope not found")  # type: ignore[attr-defined]
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_pipeline_with_two_each_steps_is_rejected(project: Project) -> None:
    from squadron.pipeline.models import PipelineDefinition, StepConfig

    two = PipelineDefinition(
        name="two",
        description="",
        params={},
        steps=[StepConfig(step_type="each", name=n, config={}) for n in ("a", "b")],
    )
    with patch("squadron.pipeline.item_resume.load_pipeline", return_value=two):
        outcome, body = await _resume(project, _req(project, "401"))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    assert "has 2 each steps; --item needs exactly one" in outcome.message  # type: ignore[attr-defined]
    body.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "not found"),
        ("{not json", "is unreadable"),
        (json.dumps({"schemaVersion": 2, "items": []}), "has schemaVersion 2"),
    ],
)
async def test_a_missing_or_bad_report_is_rejected_with_an_error(
    project: Project, content: str | None, message: str, caplog: pytest.LogCaptureFixture
) -> None:
    if content is None:
        project.report_path.unlink()
    else:
        project.report_path.write_text(content)

    with caplog.at_level("ERROR"):
        outcome, body = await _resume(project, _req(project, "401"))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    assert message in outcome.message  # type: ignore[attr-defined]
    assert any(r.levelname == "ERROR" and message in r.getMessage() for r in caplog.records)
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_held_lock_is_rejected(project: Project) -> None:
    with project_run_lock(str(project.repo)):
        outcome, body = await _resume(project, _req(project, "401"))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    assert "another squadron run holds the project lock" in outcome.message  # type: ignore[attr-defined]
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_git_dir_read_is_rejected_not_halted(project: Project) -> None:
    with patch("squadron.pipeline.run_lock.run_git", return_value=None):
        outcome, body = await _resume(project, _req(project, "401"))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unopenable_lock_file_is_rejected(project: Project) -> None:
    with patch(
        "squadron.pipeline.run_lock.Path.open", side_effect=PermissionError(13, "Permission denied")
    ):
        outcome, body = await _resume(project, _req(project, "401"))

    assert outcome.exit is ResumeExit.REJECTED  # type: ignore[attr-defined]
    assert "cannot open" in outcome.message  # type: ignore[attr-defined]
    body.assert_not_awaited()
