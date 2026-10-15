"""Usage records through the run-state round-trip (slice 175 criterion 9)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager
from squadron.providers.base import USAGE_KEY

_FIXTURES = Path(__file__).parent / "fixtures" / "state"


def _record() -> UsageRecord:
    return UsageRecord(
        model="claude-opus",
        alias="opus",
        profile="sdk",
        effort=None,
        turns=12,
        duration_seconds=84.2,
        usage=TokenUsage(prompt=412803, cached=380112, cache_write=21011, completion=9214),
        cost_usd=0.41,
        cost_basis=CostBasis.PROVIDER,
        partial=True,
    )


def test_usage_record_survives_save_and_load(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "175"})
    record = _record()
    dispatch = ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"response": "ok"},
        metadata={"model": "claude-opus", USAGE_KEY: record.to_dict()},
    )
    step = StepResult(
        step_name="design",
        step_type="phase",
        status=ExecutionStatus.COMPLETED,
        action_results=[dispatch],
    )

    manager.record_step_completed(run_id, step)
    loaded = manager.load(run_id)

    persisted = loaded.completed_steps[0].action_results[0]["metadata"]
    assert isinstance(persisted, dict)
    assert UsageRecord.from_dict(persisted[USAGE_KEY]) == record  # type: ignore[arg-type]


@pytest.mark.parametrize("version", [3, 4, 5])
def test_pre_slice_run_files_load_without_usage(tmp_path: Path, version: int) -> None:
    run_id = f"run-20260601-p4-v{version}fixture"
    shutil.copy(_FIXTURES / f"{run_id}.json", tmp_path / f"{run_id}.json")

    loaded = StateManager(runs_dir=tmp_path).load(run_id)

    assert loaded.schema_version == version
    for step in loaded.completed_steps:
        for action in step.action_results:
            metadata = action.get("metadata")
            assert isinstance(metadata, dict) and USAGE_KEY not in metadata
