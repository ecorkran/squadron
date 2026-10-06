"""Item resume works on slices-plan and tasks-plan runs with no pipeline-specific code
(slice 197 Integration Requirements; Task 28c)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    FlagKind,
    ItemDecision,
    ItemOutcome,
    ItemRerun,
)
from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.item_resume import ResumeExit, ResumeRequest, resume_item
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.state import StateManager
from tests.conftest import run_test_git
from tests.pipeline.item_resume_support import ok_action

PLAN = "500"
SLICE = 501
DESIGN = f"project-documents/user/slices/{SLICE}-slice.stub.md"
TASKS = f"project-documents/user/tasks/{SLICE}-tasks.stub.md"


def _cf(pipeline: str) -> MagicMock:
    def list_slices(plan: str | None = None) -> list[SliceEntry]:
        # slices-plan selects the slice while it has no design; afterwards (the design
        # step's post-condition) it resolves to the file the dispatch wrote.
        undesigned = pipeline == "slices-plan" and plan == PLAN
        return [SliceEntry(SLICE, "stub", None if undesigned else DESIGN, "not_started")]

    cf = MagicMock()
    cf.list_slices.side_effect = list_slices
    cf.list_tasks.return_value = [TaskEntry(SLICE, [f"{SLICE}-tasks.stub.md"], 0, 4)]
    cf.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 5", slice=str(SLICE), name="squadron"
    )
    cf.get_config.return_value = ""
    cf.list_worktrees.return_value = []
    return cf


def _setup(repo: Path, pipeline: str) -> None:
    if pipeline == "tasks-plan":
        for relative, text in {
            DESIGN: "---\ndependencies: []\n---\n",
            TASKS: "---\ndocType: tasks\n---\n",
            f"project-documents/user/reviews/{SLICE}-review.slice.stub.md": "---\nverdict: PASS\n---\n",
        }.items():
            (repo / relative).parent.mkdir(parents=True, exist_ok=True)
            (repo / relative).write_text(text)
        run_test_git(repo, "add", "-A")
        run_test_git(repo, "commit", "-q", "-m", "plan 500")


@pytest.mark.asyncio
@pytest.mark.parametrize("pipeline", ["slices-plan", "tasks-plan"])
@pytest.mark.parametrize(
    ("decision", "verdicts", "outcome"),
    [
        (ItemDecision.RETRY, ["FAIL", "PASS"], "passed"),
        (ItemDecision.ACCEPT, ["FAIL"], "accepted"),
    ],
)
async def test_item_resume_on_a_planning_batch(
    pipeline: str,
    decision: ItemDecision,
    verdicts: list[str],
    outcome: str,
    temp_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = temp_git_repo
    monkeypatch.chdir(repo)
    _setup(repo, pipeline)
    cf = _cf(pipeline)
    runs_dir = tmp_path / "runs"
    state_manager = StateManager(runs_dir=runs_dir)
    params = {k: v for k, v in load_pipeline(pipeline).params.items() if v != "required"}
    params["plan"] = PLAN
    run_id = state_manager.init_run(pipeline, params)
    report = BatchReport(pipeline, run_id, "slices", plan=PLAN)
    report.records = [
        BatchItemRecord(str(SLICE), "stub", ItemOutcome.FLAGGED, flag_kind=FlagKind.REVIEW_UNRESOLVED)
    ]
    report.write(runs_dir)
    reviews = iter(verdicts)

    async def dispatch(_ctx: ActionContext) -> ActionResult:
        for relative in (DESIGN, TASKS):
            (repo / relative).parent.mkdir(parents=True, exist_ok=True)
            (repo / relative).write_text("---\ndocType: stub\n---\n")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(_ctx: ActionContext) -> ActionResult:
        return ActionResult(success=True, action_type="review", outputs={}, verdict=next(reviews))

    dispatch_action, review_action = MagicMock(), MagicMock()
    dispatch_action.execute = dispatch
    review_action.execute = review

    async def run_body(name: str, item_params: dict[str, object], rerun: ItemRerun) -> object:
        return await execute_pipeline(
            load_pipeline(name),
            item_params,
            resolver=MagicMock(),
            cf_client=cf,
            cwd=str(repo),
            run_id=run_id,
            runs_dir=runs_dir,
            item_rerun=rerun,
            _action_registry={
                "dispatch": dispatch_action,
                "review": review_action,
                "cf-op": ok_action("cf-op"),
                "commit": ok_action("commit"),
                "summary": ok_action("summary"),
                "checkpoint": ok_action("checkpoint"),
            },
        )

    result = await resume_item(
        ResumeRequest(run_id=run_id, index=str(SLICE), decision=decision),
        cwd=str(repo),
        cf_client=cf,
        state_manager=state_manager,
        run_body=run_body,
    )

    assert result.exit is ResumeExit.RESOLVED, result.message
    record = BatchReport.load(report.json_path(runs_dir)).records[0]
    assert (record.outcome, record.decision) == (outcome, decision)
