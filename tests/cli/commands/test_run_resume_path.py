"""Resume reloads a path run from its recorded source file (slice 940 D4)."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import (
    _handle_prompt_only_next,  # pyright: ignore[reportPrivateUsage]
    _handle_step_done,  # pyright: ignore[reportPrivateUsage]
    _load_run_definition,  # pyright: ignore[reportPrivateUsage]
)
from squadron.pipeline.state import RunState, StateManager

_PIPELINE_YAML = """\
name: foo
description: {description}
steps:
  - phase: step1
"""
_BUILTIN_NAME = "slices-plan"


def _write_pipeline(path: Path, description: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_PIPELINE_YAML.format(description=description), encoding="utf-8")
    return path


def _state(manager: StateManager, name: str, pipeline_path: str | None) -> RunState:
    run_id = manager.init_run(name, {}, pipeline_path=pipeline_path)
    return manager.load(run_id)


@pytest.fixture
def manager(tmp_path: Path) -> StateManager:
    return StateManager(runs_dir=tmp_path / "runs")


def test_path_run_reloads_the_recorded_file(tmp_path: Path, manager: StateManager) -> None:
    source = _write_pipeline(tmp_path / "x" / "Foo.yaml", "before")
    state = _state(manager, "foo", str(source.resolve()))
    _write_pipeline(source, "edited after start")

    definition = _load_run_definition(state, file=sys.stderr)

    assert definition.description == "edited after start"


def test_missing_recorded_path_exits_1_without_loading_a_same_named_pipeline(
    tmp_path: Path, manager: StateManager, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "gone" / "slices-plan.yaml"
    state = _state(manager, _BUILTIN_NAME, str(missing))

    with pytest.raises(typer.Exit) as exc_info:
        _load_run_definition(state, file=sys.stderr)

    assert exc_info.value.exit_code == 1
    assert str(missing) in capsys.readouterr().err.replace("\n", "")


def test_recorded_path_that_fails_validation_exits_1_naming_the_path(
    tmp_path: Path, manager: StateManager, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "Bad.yaml"
    broken.write_text("name: bad\nsteps: not-a-list\n", encoding="utf-8")
    state = _state(manager, "bad", str(broken.resolve()))

    with pytest.raises(typer.Exit) as exc_info:
        _load_run_definition(state, file=sys.stderr)

    assert exc_info.value.exit_code == 1
    assert str(broken.resolve()) in capsys.readouterr().err.replace("\n", "")


def test_state_without_a_path_resumes_by_name(manager: StateManager) -> None:
    state = _state(manager, _BUILTIN_NAME, None)

    assert state.load_target == _BUILTIN_NAME
    with patch("squadron.cli.commands.run.load_pipeline") as load:
        _load_run_definition(state, file=sys.stderr)
    load.assert_called_once_with(_BUILTIN_NAME)


def test_pre_slice_path_run_keeps_its_name_and_loads_through_it(
    tmp_path: Path, manager: StateManager
) -> None:
    # Written before this slice: the lowercased path argument is the run name.
    legacy_name = str(tmp_path / "x" / "foo.yaml").lower()
    state = _state(manager, legacy_name, None)

    assert state.pipeline == legacy_name
    assert state.load_target == legacy_name
    assert [r.run_id for r in manager.list_runs(pipeline=legacy_name)] == [state.run_id]


def _invoke_next(run_id: str) -> None:
    _handle_prompt_only_next(run_id, None)


def _invoke_step_done(run_id: str) -> None:
    _handle_step_done(run_id, None)


def _invoke_resume(run_id: str) -> None:
    CliRunner().invoke(app, ["run", "--resume", run_id])


@pytest.mark.parametrize(
    "invoke",
    [_invoke_next, _invoke_step_done, _invoke_resume],
    ids=["prompt-only-next", "step-done", "resume"],
)
def test_every_resume_entry_point_uses_the_recorded_path(
    tmp_path: Path, manager: StateManager, invoke: Callable[[str], None]
) -> None:
    missing = tmp_path / "gone" / "slices-plan.yaml"
    state = _state(manager, _BUILTIN_NAME, str(missing))

    with (
        patch("squadron.cli.commands.run.StateManager", return_value=manager),
        patch("squadron.cli.commands.run._load_run_definition", side_effect=typer.Exit(1)) as loader,
    ):
        with contextlib.suppress(typer.Exit):  # the helper's exit(1) is stubbed in
            invoke(state.run_id)

    assert loader.call_count == 1
    assert loader.call_args.args[0].load_target == str(missing)


def test_definition_cache_loads_a_path_run_through_its_recorded_path(manager: StateManager) -> None:
    from squadron.pipeline.run_listing import DefinitionCache

    state = _state(manager, "foo", "/work/x/Foo.yaml")
    requested: list[str] = []

    def loader(target: str) -> object:
        requested.append(target)
        raise FileNotFoundError(target)

    cache = DefinitionCache(loader)  # pyright: ignore[reportArgumentType]
    assert cache.get(state) is None
    assert requested == ["/work/x/Foo.yaml"]


def test_resume_executes_the_recorded_file_not_a_same_named_pipeline(
    tmp_path: Path, manager: StateManager
) -> None:
    """Planning and execution must load the same definition (review finding)."""
    from unittest.mock import MagicMock

    from squadron.pipeline.executor import ExecutionStatus, PipelineResult

    source = _write_pipeline(tmp_path / "x" / "Foo.yaml", "mine")
    state = _state(manager, "foo", str(source.resolve()))
    done = PipelineResult(pipeline_name="foo", status=ExecutionStatus.COMPLETED, step_results=[])

    with (
        patch("squadron.cli.commands.run.StateManager", return_value=manager),
        patch("squadron.cli.commands.run._resolve_resume_iteration", return_value=0),
        patch("squadron.cli.commands.run._locked", return_value=done),
        patch("squadron.cli.commands.run._run_pipeline_sdk", new=MagicMock()) as execute,
    ):
        CliRunner().invoke(app, ["run", "--resume", state.run_id])

    assert execute.call_args.args[0] == str(source.resolve())


def test_unreadable_recorded_path_exits_1_naming_the_path(
    tmp_path: Path, manager: StateManager, capsys: pytest.CaptureFixture[str]
) -> None:
    # A directory where the file should be: open() raises IsADirectoryError.
    not_a_file = tmp_path / "Dir.yaml"
    not_a_file.mkdir()
    state = _state(manager, "dir", str(not_a_file))

    with pytest.raises(typer.Exit) as exc_info:
        _load_run_definition(state, file=sys.stderr)

    assert exc_info.value.exit_code == 1
    assert str(not_a_file) in capsys.readouterr().err.replace("\n", "")


def test_non_utf8_recorded_path_exits_1_naming_the_path(
    tmp_path: Path, manager: StateManager, capsys: pytest.CaptureFixture[str]
) -> None:
    latin1 = tmp_path / "Latin.yaml"
    latin1.write_bytes(b"name: caf\xe9\n")
    state = _state(manager, "latin", str(latin1))

    with pytest.raises(typer.Exit) as exc_info:
        _load_run_definition(state, file=sys.stderr)

    assert exc_info.value.exit_code == 1
    assert str(latin1) in capsys.readouterr().err.replace("\n", "")
