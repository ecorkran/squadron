"""tasks-plan re-reviews a tasked slice instead of regenerating it (slice 196, criterion 9)."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.batch_report import ItemOutcome
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.models import ActionContext, ActionResult

SLICE = 105
DESIGN = "project-documents/user/slices/105-slice.stub.md"
TASKS = "project-documents/user/tasks/105-tasks.stub.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.stub.md"


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Stub", design_file=DESIGN, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.stub.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 5", slice=str(SLICE), name="squadron"
    )
    client.get_config.return_value = ""
    return client


def _ok(action_type: str) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type=action_type, outputs={})
    )
    return action


def test_tasks_plan_keeps_existing_tasks_and_validates() -> None:
    definition = load_pipeline("tasks-plan")
    each = next(s for s in definition.steps if s.step_type == "each")
    body = cast(list[dict[str, dict[str, object]]], each.config["steps"])
    tasks_step = next(s["tasks"] for s in body if "tasks" in s)

    assert tasks_step["existing"] == "keep"
    assert validate_pipeline(definition) == []


@pytest.mark.asyncio
async def test_tasked_slice_without_a_tasks_review_is_re_reviewed_and_revised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for relative, text in {
        TASKS: "---\ndocType: tasks\n---\n# existing tasks\n",
        DESIGN_REVIEW: "---\ndocType: review\nverdict: PASS\n---\n",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    model_calls: list[str] = []
    real_dispatch = DispatchAction()

    class _Dispatch:
        """The step's dispatch is the real action (so it can keep); the loop's revise is fake."""

        action_type = "dispatch"

        def validate(self, config: dict[str, object]) -> list[object]:
            return []

        async def execute(self, context: ActionContext) -> ActionResult:
            if context.params.get("existing") == "keep":
                return await real_dispatch.execute(context)
            model_calls.append("revise")
            return ActionResult(success=True, action_type="dispatch", outputs={"response": "fixed"})

    verdicts = iter(["CONCERNS", "PASS"])
    reviews: list[str] = []

    async def review(_ctx: ActionContext) -> ActionResult:
        verdict = next(verdicts)
        reviews.append(verdict)
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

    review_action = MagicMock()
    review_action.execute = AsyncMock(side_effect=review)

    definition = load_pipeline("tasks-plan")
    params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}
    params["plan"] = "100"

    result = await execute_pipeline(
        definition,
        params,
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(tmp_path),
        runs_dir=tmp_path / "runs",
        _action_registry={
            "dispatch": _Dispatch(),
            "review": review_action,
            "cf-op": _ok("cf-op"),
            "checkpoint": _ok("checkpoint"),
            "commit": _ok("commit"),
            "summary": _ok("summary"),
        },
    )

    assert result.status == ExecutionStatus.COMPLETED
    report = result.step_results[0].batch_report
    assert report is not None
    assert [(r.index, r.outcome) for r in report.records] == [(str(SLICE), ItemOutcome.PASSED)]
    # The step's own dispatch kept the tasks (no model call); only the revise round called one.
    assert model_calls == ["revise"]
    # The step's review found concerns, so one revise round ran and its review passed.
    assert reviews == ["CONCERNS", "PASS"]
    assert (tmp_path / TASKS).read_text().endswith("# existing tasks\n")
