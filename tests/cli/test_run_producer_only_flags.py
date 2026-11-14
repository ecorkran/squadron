"""``--producer-only`` flag refusals and its run-state record (slice 424, Task 6)."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run_producer_only import stop_line
from squadron.pipeline.control_params import RUN_PRODUCER_ONLY
from squadron.pipeline.state import ProducerOnlyRecord, RunState, StateManager

runner = CliRunner()


def _text(result: Result) -> str:
    # Typer forces colour in CI, so strip styling and normalise wrapping before matching.
    output = result.output
    return " ".join(click.unstyle(output).split())


@pytest.mark.parametrize(
    ("extra", "flag"),
    [
        (["--from", "close-out"], "--from"),
        (["--item", "3"], "--item"),
        (["--flagged"], "--flagged"),
    ],
)
def test_refused_combination_names_both_flags(extra: list[str], flag: str) -> None:
    result = runner.invoke(app, ["run", "P6", "7", "--producer-only", *extra])

    assert result.exit_code == 1
    assert f"Error: --producer-only cannot be combined with {flag}." in _text(result)


def test_producer_only_alone_is_not_refused_by_the_flag_check() -> None:
    from squadron.cli.commands.run_producer_only import check_producer_only_flags

    check_producer_only_flags(True, from_step=None, item=None, flagged=False)
    check_producer_only_flags(False, from_step="x", item="1", flagged=True)


def test_run_state_round_trips_with_the_record(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    record = ProducerOnlyRecord(step="implement-1", skipped=["branch-0", "close-out"])

    run_id = manager.init_run("p6", {"slice": "7"}, producer_only=record)

    loaded = manager.load(run_id)
    assert loaded.producer_only == record
    assert RunState.model_validate_json(loaded.model_dump_json()).producer_only == record


def test_run_state_without_the_record_has_none(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)

    run_id = manager.init_run("p6", {"slice": "7"})

    assert manager.load(run_id).producer_only is None


def test_old_state_file_without_the_field_loads(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run(
        "p6", {"slice": "7"}, producer_only=ProducerOnlyRecord(step="s", skipped=[])
    )
    path = next(tmp_path.rglob(f"{run_id}*.json"))
    raw = json.loads(path.read_text())
    del raw["producer_only"]
    path.write_text(json.dumps(raw))

    assert manager.load(run_id).producer_only is None


def test_stop_line_with_and_without_a_commit() -> None:
    record = ProducerOnlyRecord(step="implement-1", skipped=["a", "b"])

    assert stop_line(record, "abc1234") == (
        "producer-only: stopped after implement-1 (commit abc1234); skipped: a, b"
    )
    assert stop_line(record, None) == "producer-only: stopped after implement-1; skipped: a, b"


def test_reserved_param_constant_is_what_apply_sets() -> None:
    from squadron.cli.commands.run_producer_only import apply_producer_only
    from squadron.pipeline.loader import load_pipeline

    params: dict[str, object] = {}
    selection = apply_producer_only(load_pipeline("P6"), params)

    assert params[RUN_PRODUCER_ONLY] is True
    assert len(selection.definition.steps) == 1


def test_apply_on_a_multi_producer_pipeline_exits_1_naming_candidates() -> None:
    from click.exceptions import Exit

    from squadron.cli.commands.run_producer_only import apply_producer_only
    from squadron.pipeline.loader import load_pipeline

    params: dict[str, object] = {}
    with pytest.raises(Exit) as raised:
        apply_producer_only(load_pipeline("P456"), params)

    assert raised.value.exit_code == 1
    assert RUN_PRODUCER_ONLY not in params
