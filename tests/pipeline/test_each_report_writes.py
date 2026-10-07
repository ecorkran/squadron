"""The batch report is rewritten after every item and records unreached items on a halt
(slice 197 D7)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.git_ops import GitStateUnknownError
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.sources import SOURCE_REGISTRY
from squadron.pipeline.steps import register_step_type

_HALT = "git state unverified (expected main): MERGE_HEAD present"


def _read_reports(runs_dir: Path) -> list[dict[str, object]]:
    return [json.loads(f.read_text()) for f in runs_dir.glob("*.report.json")]


async def _run(
    monkeypatch: pytest.MonkeyPatch, runs_dir: Path, seen_at_item_2: list[dict[str, object]]
) -> None:
    async def source(*_: object, **__: object) -> list[dict[str, object]]:
        return [{"index": str(i), "name": f"s{i}"} for i in (1, 2, 3, 4)]

    monkeypatch.setitem(SOURCE_REGISTRY, ("test", "halting"), source)

    async def dispatch_exec(ctx: ActionContext) -> ActionResult:
        if ctx.params["index"] == "2":
            seen_at_item_2.extend(_read_reports(runs_dir))
            raise GitStateUnknownError(_HALT)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch = MagicMock()
    dispatch.execute = dispatch_exec
    body = MagicMock()
    body.expand.return_value = [("dispatch", {"index": "{item.index}"})]
    register_step_type("_test_halting", body)
    definition = PipelineDefinition(
        name="halting",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="each",
                name="slices",
                config={
                    "source": "test.halting()",
                    "as": "item",
                    "on_item_failure": "continue",
                    "steps": [{"_test_halting": {}}],
                },
            )
        ],
    )
    await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        runs_dir=runs_dir,
        _action_registry={"dispatch": dispatch},
    )


@pytest.mark.asyncio
async def test_report_exists_after_item_1_and_a_halt_records_in_flight_and_unreached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_dir = tmp_path / "runs"
    seen: list[dict[str, object]] = []

    with pytest.raises(GitStateUnknownError):
        await _run(monkeypatch, runs_dir, seen)

    # Written after item 1, before item 2 ran.
    assert len(seen) == 1
    assert [item["index"] for item in seen[0]["items"]] == ["1"]  # type: ignore[index]

    report = json.loads(next(runs_dir.glob("*.slices.report.json")).read_text())
    outcomes = [(i["index"], i["outcome"], i["flagKind"], i["reason"]) for i in report["items"]]
    assert outcomes == [
        ("1", "passed", None, None),
        ("2", "flagged", "step_failed", _HALT),
        ("3", "not_run", None, _HALT),
        ("4", "not_run", None, _HALT),
    ]
    assert report["counts"] == {"passed": 1, "accepted": 0, "flagged": 1, "not_run": 2}
