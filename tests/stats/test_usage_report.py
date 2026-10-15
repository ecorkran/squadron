"""Tests for the ``sq stats run`` report core (slice 175 D8, D9)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.pipeline.state import StateManager
from squadron.providers.base import USAGE_KEY
from squadron.stats.usage_report import RunUsageLoadError, run_usage_report, usage_totals

_RUN = "run-20261014-p4-abcd1234"


def _record(*, cost: float | None, partial: bool = False, prompt: int = 100) -> UsageRecord:
    return UsageRecord(
        model="m",
        alias=None,
        profile="sdk",
        effort=None,
        turns=2,
        duration_seconds=3.0,
        usage=TokenUsage(prompt=prompt, completion=10),
        cost_usd=cost,
        cost_basis=None if cost is None else CostBasis.PROVIDER,
        partial=partial,
    )


def _action(action_type: str, usage: object = None) -> dict[str, object]:
    metadata: dict[str, object] = {"model": "m"}
    if usage is not None:
        metadata[USAGE_KEY] = usage
    return {"success": True, "action_type": action_type, "outputs": {}, "metadata": metadata}


def _write_run(runs_dir: Path, steps: list[dict[str, object]], run_id: str = _RUN) -> None:
    data = {
        "schema_version": 5,
        "run_id": run_id,
        "pipeline": "p4",
        "params": {"slice": 175},
        "started_at": "2026-10-14T10:00:00+00:00",
        "updated_at": "2026-10-14T10:38:12+00:00",
        "status": "completed",
        "completed_steps": [
            {
                "completed_at": "2026-10-14T10:10:00+00:00",
                "step_type": "phase",
                "status": "completed",
                **s,
            }
            for s in steps
        ],
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(data))


def test_mixed_run_totals_priced_count_and_unrecorded(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        [
            {
                "step_name": "design",
                "action_results": [
                    _action("cf-op"),
                    _action("dispatch", _record(cost=0.5).to_dict()),
                ],
            },
            {
                "step_name": "design-rev",
                "action_results": [_action("review", _record(cost=None, prompt=50).to_dict())],
            },
            {"step_name": "tasks", "action_results": [_action("dispatch")]},  # pre-slice
        ],
    )

    report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert (report.pipeline, report.slice, report.status) == ("p4", "175", "completed")
    assert [row.step for row in report.rows] == ["design", "design", "design-rev", "tasks"]
    assert report.llm_actions == 3
    assert report.unrecorded == 1
    assert report.totals.usage == TokenUsage(prompt=150, completion=20)
    assert report.totals.turns == 4
    assert (report.totals.cost_usd, report.totals.priced) == (0.5, 1)
    assert not report.any_partial


def test_malformed_usage_is_unreadable_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_run(
        tmp_path,
        [{"step_name": "design", "action_results": [_action("dispatch", {"tokens": [1, 2]})]}],
    )

    with caplog.at_level(logging.WARNING, logger="squadron.stats.usage_report"):
        report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert report.rows[0].unreadable and report.rows[0].record is None
    message = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert _RUN in message and "design" in message


def test_partial_record_sets_flag(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        [
            {
                "step_name": "x",
                "action_results": [_action("dispatch", _record(cost=None, partial=True).to_dict())],
            }
        ],
    )

    assert run_usage_report(_RUN, StateManager(runs_dir=tmp_path)).any_partial


def test_unknown_run_names_id_and_runs_dir(tmp_path: Path) -> None:
    with pytest.raises(RunUsageLoadError) as raised:
        run_usage_report("run-missing", StateManager(runs_dir=tmp_path))

    assert "run-missing" in str(raised.value) and str(tmp_path) in str(raised.value)


@pytest.mark.parametrize(
    "content",
    ["{not json", "[]", json.dumps({"schema_version": 99, "run_id": _RUN})],
    ids=["invalid-json", "not-an-object", "unsupported-schema"],
)
def test_unreadable_run_file_names_the_file(tmp_path: Path, content: str) -> None:
    (tmp_path / f"{_RUN}.json").write_text(content)

    with pytest.raises(RunUsageLoadError) as raised:
        run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert f"{_RUN}.json" in str(raised.value)


def test_loading_goes_through_state_manager(tmp_path: Path) -> None:
    _write_run(tmp_path, [])
    manager = StateManager(runs_dir=tmp_path)

    with patch.object(StateManager, "load", wraps=manager.load) as load:
        run_usage_report(_RUN, manager)

    load.assert_called_once_with(_RUN)


def test_usage_totals_empty_reports_nothing() -> None:
    totals = usage_totals([])

    assert totals.cost_usd is None and totals.turns is None and totals.priced == 0
    assert not totals.usage.reported
