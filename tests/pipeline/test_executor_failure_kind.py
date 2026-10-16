"""The executor carries a post-action failure's kind onto the dispatch result (slice 177 D4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager
from tests.pipeline.conftest import phase_artifact_cf_client


def _action(action_type: str, **outputs: object) -> MagicMock:
    impl = MagicMock()
    impl.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type=action_type, outputs=dict(outputs))
    )
    return impl


@pytest.mark.asyncio
async def test_a_dispatch_that_wrote_no_artifact_fails_with_the_artifact_missing_kind(
    tmp_path: Path,
) -> None:
    definition = PipelineDefinition(
        name="design-only",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="design",
                name="design-0",
                config={"phase": 4, "slice": "204", "model": "opus"},
            )
        ],
    )
    run_id = StateManager(runs_dir=tmp_path).init_run("design-only", {})

    result = await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=phase_artifact_cf_client(204, "204-slice.stub.md", "204-tasks.stub.md"),
        cwd=str(tmp_path),  # no artifact file exists here
        run_id=run_id,
        runs_dir=tmp_path,
        _action_registry={
            "cf-op": _action("cf-op"),
            "dispatch": _action("dispatch", response="I did nothing."),
            "commit": _action("commit"),
        },
    )

    step = result.step_results[0]
    assert step.status is ExecutionStatus.FAILED
    failed = next(a for a in step.action_results if not a.success)
    assert failed.action_type == "dispatch"
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.ARTIFACT_MISSING.value
