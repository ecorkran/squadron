"""``sq run --prompt-only --producer-only`` (slice 424, Task 8; design D3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.control_params import RUN_PRODUCER_ONLY
from squadron.pipeline.state import StateManager
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client

runner = CliRunner()


def _text(result: Result) -> str:
    return " ".join(click.unstyle(result.output).split())


def _json_of(result: Result) -> dict[str, object]:
    """The JSON object in mixed stdout/stderr output."""
    output = click.unstyle(result.output)
    return json.loads(output[output.index("{") :])


@pytest.fixture(autouse=True)
def _cf_client() -> object:  # pyright: ignore[reportUnusedFunction]
    client = phase_artifact_cf_client(7, "7-slice.x.md", "7-tasks.x.md")
    with patch("squadron.cli.commands.run.ContextForgeClient", return_value=client):
        yield client


@pytest.fixture
def slice_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "7-slice.x")
    monkeypatch.chdir(temp_git_repo)
    return temp_git_repo


def test_init_emits_only_the_producer_steps_actions(slice_repo: Path) -> None:
    result = runner.invoke(app, ["run", "P6", "7", "--prompt-only", "--producer-only"])

    assert result.exit_code == 0, result.output
    instructions = _json_of(result)
    assert instructions["step_name"] == "implement-1"
    assert instructions["total_steps"] == 1
    action_types = [action["action_type"] for action in instructions["actions"]]  # type: ignore[index]
    assert action_types == ["cf-op", "cf-op", "cf-op", "cf-op", "dispatch", "commit"]

    state = StateManager().load(str(instructions["run_id"]))
    assert state.params[RUN_PRODUCER_ONLY] is True
    assert state.producer_only is not None
    assert state.producer_only.step == "implement-1"


def test_next_after_the_step_is_done_returns_no_further_step(slice_repo: Path) -> None:
    first = runner.invoke(app, ["run", "P6", "7", "--prompt-only", "--producer-only"])
    run_id = str(_json_of(first)["run_id"])

    done = runner.invoke(app, ["run", "--step-done", run_id])
    assert done.exit_code == 0, done.output
    after = runner.invoke(app, ["run", "--prompt-only", "--next", "--resume", run_id])

    assert after.exit_code == 0, after.output
    assert _json_of(after)["status"] == "completed"
    assert "producer-only: stopped after implement-1; skipped: branch-0, close-out" in _text(after)


def test_init_off_the_slice_branch_refuses(
    temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(temp_git_repo)

    result = runner.invoke(app, ["run", "P6", "7", "--prompt-only", "--producer-only"])

    assert result.exit_code == 1
    assert "check out the branch for slice 7 first (on main)" in _text(result)
    assert StateManager().list_runs() == []


def test_max_cost_and_io_dir_stay_refused_with_prompt_only(slice_repo: Path) -> None:
    result = runner.invoke(
        app, ["run", "P6", "7", "--prompt-only", "--producer-only", "--max-cost", "1"]
    )

    assert result.exit_code == 1
    assert "--max-cost cannot be combined with --prompt-only" in _text(result)
