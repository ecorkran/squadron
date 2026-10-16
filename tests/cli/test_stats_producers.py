"""``sq stats producers`` end to end (slice 176 D8, D9, criterion 6)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.core.usage import format_usd
from squadron.pipeline.state import RunState, StateManager
from tests.stats.producer_support import action, producer_actions, run, step

runner = CliRunner()
_FLOOR_KEY = "metrology.min_evidence_n"


def _runs() -> list[RunState]:
    """Three design runs of one config (one failed), and one tasks run."""
    ok = [
        run(f"ok-{n}", [step("design-0", "design", producer_actions(verdict="PASS", cost=1.0))])
        for n in (1, 2)
    ]
    failed = run(
        "bad",
        [step("design-0", "design", producer_actions(verdict="FAIL"), status="failed")],
        status="failed",
    )
    tasks = run("tasks-1", [step("tasks-0", "tasks", [action("dispatch", model="m", profile="sdk")])])
    return [*ok, failed, tasks]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A working directory with its own config, and a runs dir holding ``_runs()``."""
    root = tmp_path / "project"
    root.mkdir()
    runs = tmp_path / "runs"
    runs.mkdir()
    for state in _runs():
        (runs / f"{state.run_id}.json").write_text(state.model_dump_json())
    monkeypatch.chdir(root)
    with patch("squadron.cli.commands.stats.StateManager", lambda: StateManager(runs_dir=runs)):
        yield runs


def _set_floor(value: str) -> None:
    (Path.cwd() / ".squadron.toml").write_text(f'"{_FLOOR_KEY}" = {value}\n', encoding="utf-8")


def _json(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["stats", "producers", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_table_and_json_agree_on_values(project: Path) -> None:
    _set_floor("2")
    table = runner.invoke(app, ["stats", "producers", "--phase", "design"])
    data = _json("--phase", "design")

    assert table.exit_code == 0, table.output
    (section,) = data["phases"]  # type: ignore[misc]
    row = section["rows"][0]
    # Three design runs of one config: two passed (cost $1.00 each), one failed.
    assert (row["n"], row["accepted"], row["failed"]) == (3, 2, 1)
    assert (row["cost_usd"], row["priced"], row["llm_actions"]) == (2.0, 2, 6)
    line = next(line for line in table.output.splitlines() if line.strip().startswith("opus"))
    assert " 2/3 " in line and " 1/3 " in line
    assert f"{format_usd(row['cost_per_accepted'])} (2 of 6 priced)" in line
    assert "Observational:" in table.output


def test_phase_filter_reports_one_phase(project: Path) -> None:
    both = [section["phase"] for section in _json()["phases"]]  # type: ignore[index, union-attr]
    only = [section["phase"] for section in _json("--phase", "tasks")["phases"]]  # type: ignore[index, union-attr]

    assert both == ["design", "tasks"] and only == ["tasks"]


def test_an_invalid_phase_exits_1_naming_the_allowed_values(project: Path) -> None:
    result = runner.invoke(app, ["stats", "producers", "--phase", "implement"])

    assert result.exit_code == 1
    assert "'implement'" in result.output and "design, tasks" in result.output


def test_a_non_integer_min_evidence_n_exits_1_naming_key_and_value(project: Path) -> None:
    _set_floor('"not-an-int"')

    result = runner.invoke(app, ["stats", "producers"])

    assert result.exit_code == 1
    assert _FLOOR_KEY in result.output and "not-an-int" in result.output


def test_rows_below_the_configured_floor_are_marked(project: Path) -> None:
    _set_floor("5")

    table = runner.invoke(app, ["stats", "producers", "--phase", "design"])

    assert "below floor" in table.output


def test_no_phase_runs_prints_a_message_and_writes_nothing(project: Path, tmp_path: Path) -> None:
    for path in project.iterdir():
        path.unlink()

    result = runner.invoke(app, ["stats", "producers"])

    assert result.exit_code == 0 and "no phase runs" in result.output
    assert list(project.iterdir()) == []
