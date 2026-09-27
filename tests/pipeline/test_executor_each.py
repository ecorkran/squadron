"""`each` failure policy and pre-flagged items (slice 195 D5).

Items come from a test source registered for the duration of each test; the
body is one registered test step whose single dispatch action is scripted
per item.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.documents.frontmatter import read_frontmatter
from squadron.pipeline.batch_report import ItemOutcome
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.sources import SOURCE_REGISTRY
from squadron.pipeline.steps import register_step_type

_OK = ActionResult(success=True, action_type="dispatch", outputs={})


def _fail(error: str | None) -> ActionResult:
    return ActionResult(success=False, action_type="dispatch", outputs={}, error=error)


_PAUSE = ActionResult(success=True, action_type="dispatch", outputs={"checkpoint": "paused"})


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    items: list[dict[str, object]],
    outcome_for: Callable[[str], ActionResult],
    policy: str | None = None,
) -> tuple[PipelineResult, list[str]]:
    """Run an ``each`` over *items*; return the result and the indices whose body ran."""

    async def source(*_: object) -> list[dict[str, object]]:
        return items

    monkeypatch.setitem(SOURCE_REGISTRY, ("test", "items"), source)
    ran: list[str] = []

    async def dispatch_exec(ctx: ActionContext) -> ActionResult:
        index = str(ctx.params["index"])
        ran.append(index)
        return outcome_for(index)

    dispatch = MagicMock()
    dispatch.execute = dispatch_exec
    body = MagicMock()
    body.expand.return_value = [("dispatch", {"index": "{item.index}"})]
    register_step_type("_test_each_policy", body)

    config: dict[str, object] = {
        "source": "test.items()",
        "as": "item",
        "steps": [{"_test_each_policy": {}}],
    }
    if policy is not None:
        config["on_item_failure"] = policy
    definition = PipelineDefinition(
        name="each-policy",
        description="test",
        params={},
        steps=[StepConfig(step_type="each", name="slices", config=config)],
    )
    result = await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"dispatch": dispatch},
    )
    return result, ran


def _items(*indices: str, **flags: str) -> list[dict[str, object]]:
    return [
        {
            "index": i,
            "name": f"slice-{i}",
            **({"flag_reason": flags[f"f{i}"]} if f"f{i}" in flags else {}),
        }
        for i in indices
    ]


class TestContinuePolicy:
    @pytest.mark.asyncio
    async def test_failed_item_is_flagged_and_next_item_runs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="squadron.pipeline.executor")

        result, ran = await _run(
            monkeypatch,
            _items("1", "2"),
            lambda i: _fail("provider quota exceeded") if i == "1" else _OK,
            policy="continue",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert ran == ["1", "2"]
        assert "item 1 FLAGGED: provider quota exceeded" in caplog.text

    @pytest.mark.asyncio
    async def test_pause_stops_the_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")

        result, ran = await _run(monkeypatch, _items("1", "2"), lambda i: _PAUSE, policy="continue")

        assert result.status == ExecutionStatus.PAUSED
        assert ran == ["1"]


class TestStopPolicy:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("policy", [None, "stop"])
    async def test_failed_item_fails_the_step(
        self, monkeypatch: pytest.MonkeyPatch, policy: str | None
    ) -> None:
        result, ran = await _run(monkeypatch, _items("1", "2"), lambda i: _fail("boom"), policy)

        assert result.status == ExecutionStatus.FAILED
        assert ran == ["1"]


class TestPreFlaggedItems:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("policy", [None, "continue"])
    async def test_flagged_item_body_never_runs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        policy: str | None,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="squadron.pipeline.executor")

        result, ran = await _run(
            monkeypatch,
            _items("1", "2", f1="no design review found"),
            lambda i: _OK,
            policy,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert ran == ["2"]
        assert "item 1 FLAGGED: no design review found" in caplog.text


class TestItemFailureReason:
    def _failed(self, error: str | None, actions: list[ActionResult]) -> StepResult:
        return StepResult(
            step_name="design",
            step_type="design",
            status=ExecutionStatus.FAILED,
            action_results=actions,
            error=error,
        )

    def test_step_error_first(self) -> None:
        from squadron.pipeline.executor import _item_failure_reason

        assert _item_failure_reason(self._failed("step broke", [_fail("action broke")])) == "step broke"

    def test_then_first_failed_action_error(self) -> None:
        from squadron.pipeline.executor import _item_failure_reason

        actions = [_OK, _fail(None), _fail("first real error"), _fail("second")]
        assert _item_failure_reason(self._failed(None, actions)) == "first real error"

    def test_then_generic_line(self) -> None:
        from squadron.pipeline.executor import _item_failure_reason

        assert _item_failure_reason(self._failed(None, [_fail(None)])) == "step design failed"


class TestBatchReportWiring:
    @pytest.mark.asyncio
    async def test_mixed_run_writes_report_with_counts(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # conftest points the default runs dir at tmp_path / "runs".
        outcomes = {"1": _OK, "2": _fail("provider quota exceeded")}
        result, _ = await _run(
            monkeypatch,
            _items("1", "2", "3", f3="no design review found"),
            lambda i: outcomes[i],
            policy="continue",
        )

        report = result.step_results[0].batch_report
        assert report is not None
        path = report.path(tmp_path / "runs")
        assert path.is_file()
        assert path.name.endswith(".slices.report.md")
        assert read_frontmatter(path) == {
            "docType": "batch-report",
            "pipeline": "each-policy",
            "runId": report.run_id,
            "passed": 1,
            "accepted": 0,
            "flagged": 2,
        }
        assert [(r.index, r.outcome.value, r.reason) for r in report.records] == [
            ("1", "passed", None),
            ("2", "flagged", "provider quota exceeded"),
            ("3", "flagged", "no design review found"),
        ]

    @pytest.mark.asyncio
    async def test_report_written_when_every_item_is_flagged(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        result, ran = await _run(
            monkeypatch, _items("1", "2"), lambda i: _fail("boom"), policy="continue"
        )

        report = result.step_results[0].batch_report
        assert report is not None
        assert ran == ["1", "2"]
        assert report.count(ItemOutcome.FLAGGED) == 2
        assert report.path(tmp_path / "runs").is_file()

    @pytest.mark.asyncio
    async def test_stopped_run_still_writes_report(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        result, _ = await _run(monkeypatch, _items("1", "2"), lambda i: _fail("boom"))

        report = result.step_results[0].batch_report
        assert result.status == ExecutionStatus.FAILED
        assert report is not None
        assert [r.index for r in report.records] == ["1"]
        assert report.path(tmp_path / "runs").is_file()
