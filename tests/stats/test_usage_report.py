"""Tests for the ``sq stats run`` report core (slice 175 D8, D9)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import StepTypeName
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


def _write_run(
    runs_dir: Path,
    steps: list[dict[str, object]],
    run_id: str = _RUN,
    *,
    status: str = "completed",
    current_step: str | None = None,
) -> None:
    data = {
        "schema_version": 5,
        "run_id": run_id,
        "pipeline": "p4",
        "params": {"slice": 175},
        "started_at": "2026-10-14T10:00:00+00:00",
        "updated_at": "2026-10-14T10:38:12+00:00",
        "status": status,
        "current_step": current_step,
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


def _loop_step(
    prior: list[list[dict[str, object]]] | None, final: list[dict[str, object]], iteration: int
) -> dict[str, object]:
    step: dict[str, object] = {
        "step_name": "rounds",
        "step_type": StepTypeName.LOOP.value,
        "action_results": final,
        "iteration": iteration,
    }
    if prior is not None:
        step["prior_round_results"] = prior
    return step


def test_loop_rows_carry_rounds_and_totals_cover_every_round(tmp_path: Path) -> None:
    round_one = [_action("review", _record(cost=0.1, prompt=100).to_dict())]
    round_two = [_action("review", _record(cost=0.2, prompt=200).to_dict())]
    _write_run(tmp_path, [_loop_step([round_one], round_two, iteration=2)])

    report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert [row.round for row in report.rows] == [1, 2]
    assert report.totals.usage.prompt == 300
    assert (report.totals.cost_usd, report.totals.priced) == (pytest.approx(0.3), 2)  # type: ignore[comparison-overlap]
    assert not report.partial_loop


def test_non_loop_rows_have_no_round(tmp_path: Path) -> None:
    _write_run(tmp_path, [{"step_name": "design", "action_results": [_action("dispatch")]}])

    report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert [row.round for row in report.rows] == [None]


def test_pre_176_loop_file_keeps_rows_and_totals(tmp_path: Path) -> None:
    final = [_action("review", _record(cost=0.2, prompt=200).to_dict())]
    _write_run(tmp_path, [_loop_step(None, final, iteration=2)])

    report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert [row.action_type for row in report.rows] == ["review"]
    assert report.totals.usage.prompt == 200
    assert (report.totals.cost_usd, report.totals.priced) == (0.2, 1)


def test_malformed_usage_in_earlier_round_is_unreadable_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    earlier = [_action("review", {"tokens": [1, 2]})]
    final = [_action("review", _record(cost=0.2).to_dict())]
    _write_run(tmp_path, [_loop_step([earlier], final, iteration=2)])

    with caplog.at_level(logging.WARNING, logger="squadron.stats.usage_report"):
        report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert report.rows[0].unreadable and report.rows[0].round == 1
    assert report.rows[1].record is not None and report.rows[1].round == 2
    message = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert _RUN in message and "rounds" in message


@pytest.mark.parametrize(
    ("status", "partial"), [("failed", True), ("paused", True), ("completed", False)]
)
def test_partial_loop_is_a_stopped_run_on_a_loop_step(
    tmp_path: Path, status: str, partial: bool
) -> None:
    final = [_action("review", _record(cost=0.2).to_dict())]
    _write_run(tmp_path, [_loop_step(None, final, iteration=1)], status=status, current_step="rounds")

    report = run_usage_report(_RUN, StateManager(runs_dir=tmp_path))

    assert report.partial_loop is partial


def test_failed_run_on_a_non_loop_step_is_not_partial_loop(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        [{"step_name": "design", "action_results": [_action("dispatch")]}],
        status="failed",
        current_step="design",
    )

    assert not run_usage_report(_RUN, StateManager(runs_dir=tmp_path)).partial_loop
