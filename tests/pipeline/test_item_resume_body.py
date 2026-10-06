"""Item resume reruns one item's body and replaces its record (slice 197 D8, D9, Task 28c;
criteria 6, 7, 8, 15)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.pipeline.batch_report import ItemDecision
from squadron.pipeline.git_ops import GitStateUnknownError
from squadron.pipeline.item_resume import ResumeExit
from tests.conftest import run_test_git
from tests.pipeline.item_resume_support import BodyFakes, Project, branch, make_project, resume

_INSTRUCTIONS = "Keep the CLI flags unchanged; fix only what the review lists."
_BLOCK = "--- Instructions from checkpoint resolution ---"


@pytest.fixture
def project(temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    monkeypatch.chdir(temp_git_repo)
    return make_project(temp_git_repo, tmp_path / "runs")


def _merges(project: Project) -> list[str]:
    log = run_test_git(project.repo, "log", "--first-parent", "--format=%s", "main")
    return [s for s in log.splitlines() if s.startswith("merge: slice")]


@pytest.mark.asyncio
async def test_retry_keeps_the_work_revises_with_the_instructions_and_merges(
    project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    fakes = BodyFakes(verdicts=["CONCERNS", "PASS"])
    caplog.set_level(logging.INFO, logger="squadron.pipeline.actions.dispatch")

    outcome = await resume(
        project,
        "401",
        ItemDecision.RETRY,
        fakes,
        instructions=_INSTRUCTIONS,
        overrides={"accept-threshold": "review.pass"},
    )

    assert outcome.exit is ResumeExit.RESOLVED
    assert [kind for kind, _ in fakes.dispatch_prompts] == ["revise"]  # implement kept
    assert any(
        f"keeps existing work on {branch(401)} (1 commits ahead of main)" in r.getMessage()
        for r in caplog.records
    )
    prompt = str(fakes.dispatch_prompts[0][1]["prompt"])
    assert prompt.startswith(f"{_BLOCK}\n{_INSTRUCTIONS}")
    assert _merges(project) == ["merge: slice 401 — S401"]
    record = project.record("401")
    assert (record.outcome, record.decision, record.flag_kind) == ("passed", "retry", None)
    assert record.resumed_at
    # The other records are untouched.
    assert [r.index for r in project.report().records] == ["401", "402", "403", "404"]
    assert project.record("402").decision is None


@pytest.mark.asyncio
async def test_accept_reviews_once_runs_no_rounds_and_merges(project: Project) -> None:
    fakes = BodyFakes(verdicts=["FAIL"])

    outcome = await resume(project, "401", ItemDecision.ACCEPT, fakes)

    assert outcome.exit is ResumeExit.RESOLVED
    assert fakes.dispatch_prompts == []
    assert fakes.reviews == 1
    assert _merges(project) == ["merge: slice 401 — S401"]
    record = project.record("401")
    assert (record.outcome, record.decision, record.final_verdict) == ("accepted", "accept", "FAIL")


@pytest.mark.asyncio
async def test_a_retry_flagged_again_replaces_the_record(project: Project) -> None:
    fakes = BodyFakes(verdicts=["FAIL"])

    outcome = await resume(project, "401", ItemDecision.RETRY, fakes)

    assert outcome.exit is ResumeExit.FLAGGED
    assert _merges(project) == []
    record = project.record("401")
    assert (record.outcome, record.flag_kind, record.failed_step, record.decision) == (
        "flagged",
        "review_unresolved",
        "revise-code",
        "retry",
    )


@pytest.mark.asyncio
async def test_retry_on_a_not_run_item_runs_its_body(project: Project) -> None:
    fakes = BodyFakes(verdicts=["PASS"])

    outcome = await resume(project, "404", ItemDecision.RETRY, fakes)

    assert outcome.exit is ResumeExit.RESOLVED
    assert [kind for kind, _ in fakes.dispatch_prompts] == ["implement"]
    assert _merges(project) == ["merge: slice 404 — S404"]
    assert project.record("404").outcome == "passed"


@pytest.mark.asyncio
async def test_an_unknown_git_state_mid_item_halts(
    project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    fakes = BodyFakes(verdicts=["PASS"])

    async def review(_ctx: object) -> object:
        raise GitStateUnknownError("git state unverified (expected main): MERGE_HEAD present")

    fakes.review = review  # type: ignore[method-assign]
    with caplog.at_level(logging.ERROR):
        outcome = await resume(project, "401", ItemDecision.RETRY, fakes)

    assert outcome.exit is ResumeExit.HALTED
    assert "MERGE_HEAD present" in outcome.message
    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.asyncio
async def test_a_failed_report_rewrite_halts_and_keeps_the_old_report(
    project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    before = project.report_path.read_text()
    fakes = BodyFakes(verdicts=["PASS"])

    with (
        patch(
            "squadron.pipeline.batch_report.Path.replace",
            side_effect=OSError(28, "No space left on device"),
        ),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.batch_report"),
    ):
        outcome = await resume(project, "401", ItemDecision.RETRY, fakes)

    assert outcome.exit is ResumeExit.HALTED
    assert project.report_path.read_text() == before
    assert any(
        r.levelno == logging.ERROR and "cannot write batch report" in r.getMessage()
        for r in caplog.records
    )
