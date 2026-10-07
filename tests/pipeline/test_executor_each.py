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
from squadron.pipeline.state import _default_runs_dir  # pyright: ignore[reportPrivateUsage]
from squadron.pipeline.steps import register_step_type
from tests.pipeline.observer_support import RecordingObserver

_OK = ActionResult(success=True, action_type="dispatch", outputs={})


def _fail(error: str | None) -> ActionResult:
    return ActionResult(success=False, action_type="dispatch", outputs={}, error=error)


_PAUSE = ActionResult(success=True, action_type="dispatch", outputs={"checkpoint": "paused"})


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    items: list[dict[str, object]],
    outcome_for: Callable[[str], ActionResult],
    policy: str | None = None,
    observer: RecordingObserver | None = None,
) -> tuple[PipelineResult, list[str]]:
    """Run an ``each`` over *items*; return the result and the indices whose body ran."""

    async def source(*_: object, **__: object) -> list[dict[str, object]]:
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
        observer=observer,
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


class TestObserverCallOrder:
    @pytest.mark.asyncio
    async def test_each_step_reports_every_item_between_start_and_completion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observer = RecordingObserver()

        await _run(monkeypatch, _items("180", "181", "182"), lambda _: _OK, observer=observer)

        assert [(kind, name) for kind, name, _ in observer.events] == [
            ("step_started", "slices"),
            ("item_started", "slices"),
            ("item_started", "slices"),
            ("item_started", "slices"),
            ("step_completed", "slices"),
        ]
        items = [item for _, _, item in observer.events if item is not None]
        assert [(i.position, i.total, i.index) for i in items] == [
            (0, 3, "180"),
            (1, 3, "181"),
            (2, 3, "182"),
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
    async def test_mixed_run_writes_report_with_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The hermetic HOME fixture (conftest) keeps the default runs dir per test.
        outcomes = {"1": _OK, "2": _fail("provider quota exceeded")}
        result, _ = await _run(
            monkeypatch,
            _items("1", "2", "3", f3="no design review found"),
            lambda i: outcomes[i],
            policy="continue",
        )

        report = result.step_results[0].batch_report
        assert report is not None
        path = report.path(_default_runs_dir())
        assert path.is_file()
        assert path.name.endswith(".slices.report.md")
        assert read_frontmatter(path) == {
            "docType": "batch-report",
            "pipeline": "each-policy",
            "runId": report.run_id,
            "passed": 1,
            "accepted": 0,
            "flagged": 2,
            "not_run": 0,
        }
        assert [(r.index, r.outcome.value, r.reason) for r in report.records] == [
            ("1", "passed", None),
            ("2", "flagged", "provider quota exceeded"),
            ("3", "flagged", "no design review found"),
        ]

    @pytest.mark.asyncio
    async def test_report_written_when_every_item_is_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, ran = await _run(
            monkeypatch, _items("1", "2"), lambda i: _fail("boom"), policy="continue"
        )

        report = result.step_results[0].batch_report
        assert report is not None
        assert ran == ["1", "2"]
        assert report.count(ItemOutcome.FLAGGED) == 2
        assert report.path(_default_runs_dir()).is_file()

    @pytest.mark.asyncio
    async def test_stopped_run_still_writes_report(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result, _ = await _run(monkeypatch, _items("1", "2"), lambda i: _fail("boom"))

        report = result.step_results[0].batch_report
        assert result.status == ExecutionStatus.FAILED
        assert report is not None
        assert [r.index for r in report.records] == ["1"]
        assert report.path(_default_runs_dir()).is_file()


class TestUnusableSessionInBatch:
    @pytest.mark.asyncio
    async def test_items_after_failed_reconnect_are_flagged_unusable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Slice 932 D13: a failed rotate reconnect leaves the session unusable;
        later items are flagged with that reason and never reach query()."""
        from squadron.pipeline.actions.compact import CompactAction
        from squadron.pipeline.actions.dispatch import DispatchAction
        from tests.pipeline.conftest import (
            ScriptedClient,
            failing_reconnect_patch,
            scripted_session,
            sdk_result,
            sdk_text,
        )

        caplog.set_level(logging.WARNING, logger="squadron.pipeline.executor")

        async def source(*_: object, **__: object) -> list[dict[str, object]]:
            return _items("1", "2", "3")

        monkeypatch.setitem(SOURCE_REGISTRY, ("test", "items"), source)
        body = MagicMock()
        body.expand.return_value = [("dispatch", {"prompt": "work {item.index}"}), ("compact", {})]
        register_step_type("_test_each_unusable", body)
        definition = PipelineDefinition(
            name="each-unusable",
            description="test",
            params={},
            steps=[
                StepConfig(
                    step_type="each",
                    name="slices",
                    config={
                        "source": "test.items()",
                        "as": "item",
                        "steps": [{"_test_each_unusable": {}}],
                        "on_item_failure": "continue",
                    },
                )
            ],
        )
        client = ScriptedClient([sdk_text("did 1"), sdk_result()], [sdk_text("SUM"), sdk_result()])
        session = scripted_session(client)
        resolver = MagicMock()
        resolver.resolve.return_value = ("model-id", None)

        with failing_reconnect_patch() as fresh_ctor:
            result = await execute_pipeline(
                definition,
                {"_project": "test"},
                resolver=resolver,
                cf_client=MagicMock(),
                sdk_session=session,  # type: ignore[arg-type]
                _action_registry={"dispatch": DispatchAction(), "compact": CompactAction()},
            )

        report = result.step_results[0].batch_report
        assert report is not None
        reasons = {r.index: r.reason or "" for r in report.records}
        assert "E2BIG" in reasons["1"]
        assert "SDK session unusable" in reasons["2"]
        assert "SDK session unusable" in reasons["3"]
        assert "item 2 FLAGGED: SDK session unusable" in caplog.text
        fresh_ctor.return_value.query.assert_not_called()


class TestFinalTextInBatchFlags:
    @pytest.mark.asyncio
    async def test_flag_reason_carries_agents_final_text(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        """Slice 932 D7: a phase dispatch with no artifact inside an ``each``
        is flagged with the agent's last words in the report and the warning."""
        from unittest.mock import AsyncMock

        from squadron.pipeline.state import StateManager
        from tests.pipeline.conftest import phase_artifact_cf_client

        caplog.set_level(logging.WARNING, logger="squadron.pipeline.executor")

        async def source(*_: object, **__: object) -> list[dict[str, object]]:
            return _items("204")

        monkeypatch.setitem(SOURCE_REGISTRY, ("test", "items"), source)
        response = "Launched a research agent; it is still running."
        dispatch = MagicMock()
        dispatch.execute = AsyncMock(
            return_value=ActionResult(
                success=True, action_type="dispatch", outputs={"response": response}
            )
        )
        cf_op = MagicMock()
        cf_op.execute = AsyncMock(
            return_value=ActionResult(success=True, action_type="cf-op", outputs={})
        )
        commit = MagicMock()
        commit.execute = AsyncMock(
            return_value=ActionResult(success=True, action_type="commit", outputs={})
        )
        definition = PipelineDefinition(
            name="each-final-text",
            description="test",
            params={},
            steps=[
                StepConfig(
                    step_type="each",
                    name="slices",
                    config={
                        "source": "test.items()",
                        "as": "item",
                        "on_item_failure": "continue",
                        "steps": [{"design": {"phase": 4, "slice": "{item.index}", "model": "opus"}}],
                    },
                )
            ],
        )
        run_id = StateManager(runs_dir=tmp_path).init_run("each-final-text", {})

        result = await execute_pipeline(
            definition,
            {"_project": "test"},
            resolver=MagicMock(),
            cf_client=phase_artifact_cf_client(204, "204-slice.stub.md", "204-tasks.stub.md"),
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            _action_registry={"cf-op": cf_op, "dispatch": dispatch, "commit": commit},
        )

        report = result.step_results[0].batch_report
        assert report is not None
        reason = report.records[0].reason or ""
        assert report.records[0].outcome is ItemOutcome.FLAGGED
        assert f'agent\'s final text: "{response}"' in reason
        assert "item 204 FLAGGED:" in caplog.text
        assert "agent's final text:" in caplog.text


def _dep_items(*specs: tuple[str, list[int]], **flags: str) -> list[dict[str, object]]:
    """Items with ``dependencies``, in run order; ``f{index}=reason`` pre-flags an item."""
    return [
        {
            "index": index,
            "name": f"slice-{index}",
            "dependencies": deps,
            **({"flag_reason": flags[f"f{index}"]} if f"f{index}" in flags else {}),
        }
        for index, deps in specs
    ]


def _records(result: PipelineResult) -> list[tuple[str, str, str | None]]:
    report = result.step_results[0].batch_report
    assert report is not None
    return [(r.index, r.outcome.value, r.reason) for r in report.records]


class TestDependencyFlags:
    """Slice 196 D10: a dependent of a flagged item is flagged without running."""

    @pytest.mark.asyncio
    async def test_direct_dependent_is_flagged_and_its_body_never_runs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, ran = await _run(
            monkeypatch,
            _dep_items(("1", []), ("2", [1])),
            lambda i: _fail("boom") if i == "1" else _OK,
            policy="continue",
        )

        assert ran == ["1"]
        assert _records(result) == [
            ("1", "flagged", "boom"),
            ("2", "flagged", "dependency 1 flagged"),
        ]

    @pytest.mark.asyncio
    async def test_flags_propagate_transitively_in_run_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, ran = await _run(
            monkeypatch,
            _dep_items(("1", []), ("2", [1]), ("3", [2])),
            lambda i: _fail("boom") if i == "1" else _OK,
            policy="continue",
        )

        assert ran == ["1"]
        assert _records(result)[2] == ("3", "flagged", "dependency 2 flagged")

    @pytest.mark.asyncio
    async def test_an_independent_item_still_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result, ran = await _run(
            monkeypatch,
            _dep_items(("1", []), ("2", [1]), ("3", [])),
            lambda i: _fail("boom") if i == "1" else _OK,
            policy="continue",
        )

        assert ran == ["1", "3"]
        assert [r[1] for r in _records(result)] == ["flagged", "flagged", "passed"]

    @pytest.mark.asyncio
    async def test_a_dependency_outside_the_run_flags_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, ran = await _run(monkeypatch, _dep_items(("2", [99])), lambda i: _OK, policy="continue")

        assert ran == ["2"]

    @pytest.mark.asyncio
    async def test_a_dependency_that_comes_later_does_not_flag_its_dependent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, ran = await _run(
            monkeypatch,
            _dep_items(("1", [2]), ("2", [])),
            lambda i: _fail("boom") if i == "2" else _OK,
            policy="continue",
        )

        assert ran == ["1", "2"]
        assert [r[1] for r in _records(result)] == ["passed", "flagged"]

    @pytest.mark.asyncio
    async def test_several_flagged_dependencies_are_joined(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, _ = await _run(
            monkeypatch,
            _dep_items(("1", []), ("2", []), ("3", [1, 2])),
            lambda i: _fail("boom") if i in {"1", "2"} else _OK,
            policy="continue",
        )

        assert _records(result)[2] == (
            "3",
            "flagged",
            "dependency 1 flagged; dependency 2 flagged",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("policy", ["continue", "stop"])
    async def test_a_pre_flagged_item_flags_its_dependents_under_both_policies(
        self, monkeypatch: pytest.MonkeyPatch, policy: str
    ) -> None:
        result, ran = await _run(
            monkeypatch,
            _dep_items(("1", []), ("2", [1]), ("3", []), f1="design review below threshold"),
            lambda i: _OK,
            policy=policy,
        )

        assert ran == ["3"]
        assert _records(result)[:2] == [
            ("1", "flagged", "design review below threshold"),
            ("2", "flagged", "dependency 1 flagged"),
        ]

    @pytest.mark.asyncio
    async def test_items_without_dependencies_are_unaffected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, ran = await _run(
            monkeypatch,
            _items("1", "2"),
            lambda i: _fail("boom") if i == "1" else _OK,
            policy="continue",
        )

        assert ran == ["1", "2"]


# ---------------------------------------------------------------------------
# Flag kinds (slice 197 D7)
# ---------------------------------------------------------------------------


def _branch_failure(failure: str) -> ActionResult:
    return ActionResult(
        success=False, action_type="branch", outputs={"failure": failure}, error="merge failed"
    )


def _record(result: PipelineResult, index: str):  # type: ignore[no-untyped-def]
    report = result.step_results[0].batch_report
    assert report is not None
    return next(r for r in report.records if r.index == index)


class TestFlagKinds:
    @pytest.mark.asyncio
    async def test_a_source_flag_without_a_kind_is_not_ready(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, _ = await _run(monkeypatch, _items("1", f1="no task file"), lambda i: _OK, "continue")

        record = _record(result, "1")
        assert (record.flag_kind, record.failed_step, record.branch) == ("not_ready", None, None)

    @pytest.mark.asyncio
    async def test_a_source_flag_kind_is_carried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        items = [{"index": "2", "flag_reason": "dependency 1 not designed", "flag_kind": "dependency"}]

        result, _ = await _run(monkeypatch, items, lambda i: _OK, "continue")

        assert _record(result, "2").flag_kind == "dependency"

    @pytest.mark.asyncio
    async def test_a_flagged_dependency_is_dependency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        items = [{"index": "1"}, {"index": "2", "dependencies": [1]}]

        result, ran = await _run(monkeypatch, items, lambda i: _fail("boom"), "continue")

        assert ran == ["1"]
        assert _record(result, "2").flag_kind == "dependency"

    @pytest.mark.asyncio
    async def test_a_failed_step_is_step_failed_with_its_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, _ = await _run(monkeypatch, _items("1"), lambda i: _fail("boom"), "continue")

        record = _record(result, "1")
        assert record.flag_kind == "step_failed"
        assert record.failed_step is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("failure", "kind"), [("conflict", "branch_conflict"), ("other", "step_failed")]
    )
    async def test_each_branch_failure_class(
        self, monkeypatch: pytest.MonkeyPatch, failure: str, kind: str
    ) -> None:
        result, _ = await _run(monkeypatch, _items("1"), lambda i: _branch_failure(failure), "continue")

        assert _record(result, "1").flag_kind == kind

    @pytest.mark.asyncio
    async def test_a_pause_is_paused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")

        result, _ = await _run(monkeypatch, _items("1"), lambda i: _PAUSE, "continue")

        assert _record(result, "1").flag_kind == "paused"

    @pytest.mark.asyncio
    async def test_the_entered_branch_is_recorded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def outcome(_: str) -> ActionResult:
            return ActionResult(success=True, action_type="branch", outputs={"branch": "1-slice.one"})

        result, _ = await _run(monkeypatch, _items("1"), outcome, "continue")

        assert _record(result, "1").branch == "1-slice.one"


def _step(status: ExecutionStatus, actions: list[ActionResult], exhausted: bool = False) -> StepResult:
    return StepResult(
        step_name="s", step_type="t", status=status, action_results=actions, exhausted=exhausted
    )


@pytest.mark.parametrize(
    ("final", "kind"),
    [
        (_step(ExecutionStatus.FAILED, [], exhausted=True), "review_unresolved"),
        (_step(ExecutionStatus.PAUSED, [], exhausted=True), "paused"),
        (_step(ExecutionStatus.FAILED, [_branch_failure("conflict")]), "branch_conflict"),
        (_step(ExecutionStatus.FAILED, [_branch_failure("other")]), "step_failed"),
        (_step(ExecutionStatus.FAILED, [_fail("no arch 999")]), "step_failed"),
    ],
)
def test_flag_kind_classifies_the_final_step(final: StepResult, kind: str) -> None:
    from squadron.pipeline.executor import _flag_kind  # pyright: ignore[reportPrivateUsage]

    assert _flag_kind(final) == kind


class TestSourceReceivesCwd:
    @pytest.mark.asyncio
    async def test_executor_hands_the_source_its_effective_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        seen: list[str] = []

        async def source(*_: object, cwd: str) -> list[dict[str, object]]:
            seen.append(cwd)
            return []

        monkeypatch.setitem(SOURCE_REGISTRY, ("test", "cwd"), source)
        definition = PipelineDefinition(
            name="each-cwd",
            description="test",
            params={},
            steps=[
                StepConfig(
                    step_type="each",
                    name="slices",
                    config={"source": "test.cwd()", "as": "item", "steps": []},
                )
            ],
        )
        await execute_pipeline(
            definition,
            {"_project": "test"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            cwd=str(tmp_path),
            _action_registry={},
        )
        assert seen == [str(tmp_path)]
