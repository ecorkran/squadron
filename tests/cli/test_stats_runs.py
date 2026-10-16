"""``sq stats runs`` end to end (slice 176 D7, criterion 7)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.core.usage import format_usd
from squadron.pipeline.state import StateManager
from tests.stats.producer_support import action, producer_actions, run, step

runner = CliRunner()


def _day(day: int) -> datetime:
    return datetime(2026, 11, day, 9, tzinfo=UTC)


@pytest.fixture
def runs_dir(tmp_path: Path) -> Iterator[Path]:
    """p4 on slice 1 ($1), p5 on slice 1 ($2, stopped in a loop), p4 on slice 2 (no cost)."""
    directory = tmp_path / "runs"
    directory.mkdir()
    states = [
        run(
            "p4-s1",
            [step("design-0", "design", producer_actions(cost=1.0))],
            slice_index=1,
            started_at=_day(1),
        ),
        run(
            "p5-s1",
            [
                step("tasks-0", "tasks", producer_actions(cost=2.0)),
                step("loop-1", "loop", status="failed"),
            ],
            pipeline="p5",
            slice_index=1,
            status="failed",
            current_step="loop-1",
            started_at=_day(2),
        ),
        run(
            "p4-s2",
            [step("design-0", "design", [action("dispatch"), action("review")])],
            slice_index=2,
            started_at=_day(3),
        ),
    ]
    for state in states:
        (directory / f"{state.run_id}.json").write_text(state.model_dump_json())
    with patch("squadron.cli.commands.stats.StateManager", lambda: StateManager(runs_dir=directory)):
        yield directory


def _json(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["stats", "runs", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_table_and_json_show_the_same_rows_and_total(runs_dir: Path) -> None:
    table = runner.invoke(app, ["stats", "runs"])
    data = _json()

    assert table.exit_code == 0, table.output
    rows = data["rows"]
    assert isinstance(rows, list) and [row["run_id"] for row in rows] == ["p4-s2", "p5-s1", "p4-s1"]
    for row in rows:
        assert row["run_id"] in table.output
    total = data["totals"]["cost_usd"]  # type: ignore[index]
    assert total == 3.0
    assert f"{format_usd(total)} (2 of 6 priced)" in table.output
    assert "1 run(s): partial loop not recorded" in table.output
    assert [row["partial_loop"] for row in rows] == [False, True, False]


def test_the_slice_and_pipeline_filters_narrow_the_rows(runs_dir: Path) -> None:
    by_slice = [row["run_id"] for row in _json("--slice", "1")["rows"]]  # type: ignore[union-attr, index]
    by_pipeline = [row["run_id"] for row in _json("--pipeline", "p4")["rows"]]  # type: ignore[union-attr, index]
    both = [row["run_id"] for row in _json("--slice", "1", "--pipeline", "p4")["rows"]]  # type: ignore[union-attr, index]

    assert by_slice == ["p5-s1", "p4-s1"]
    assert by_pipeline == ["p4-s2", "p4-s1"]
    assert both == ["p4-s1"]


def test_no_matching_runs_prints_a_message_and_exits_0(runs_dir: Path) -> None:
    result = runner.invoke(app, ["stats", "runs", "--slice", "99"])

    assert result.exit_code == 0 and "no matching runs" in result.output


def test_a_run_with_no_cost_shows_a_dash_not_zero(runs_dir: Path) -> None:
    table = runner.invoke(app, ["stats", "runs", "--slice", "2"])

    row = next(line for line in table.output.splitlines() if line.strip().startswith("p4-s2"))
    assert row.rstrip().endswith("—") and "$0" not in row


def test_the_command_writes_nothing(runs_dir: Path) -> None:
    before = sorted(path.name for path in runs_dir.iterdir())

    for args in (["runs"], ["runs", "--json"], ["runs", "--slice", "1"]):
        assert runner.invoke(app, ["stats", *args]).exit_code == 0

    assert sorted(path.name for path in runs_dir.iterdir()) == before
