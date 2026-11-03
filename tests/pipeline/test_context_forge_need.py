"""The Context Forge pre-flight runs only for pipelines with a step that calls cf (#288)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from squadron.cli.commands.run import _run_pipeline
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps import StepTypeName, bootstrap_step_types, get_step_type
from squadron.pipeline.steps.utils import any_step_needs_context_forge

_DISPATCH_ONLY = """\
name: no-cf
description: Dispatch-only pipeline

steps:
  - dispatch:
      name: answer
      prompt: "Say hi."
  - compact:
"""

_DISPATCH_WITH_ARTIFACT = """\
name: artifact-cf
description: A dispatch that declares an artifact kind

params:
  slice: required

steps:
  - dispatch:
      name: write-design
      prompt: "Write it."
      artifact: design
"""

_WITH_BRANCH = """\
name: branch-cf
description: A branch step

params:
  slice: required

steps:
  - branch: { op: enter }
"""


def _step(step_type: str, name: str = "s", **config: object) -> StepConfig:
    return StepConfig(step_type=step_type, name=name, config=dict(config))


def test_every_built_in_step_type_declares_its_answer() -> None:
    # The built-in names, not list_step_types(): other tests register fakes globally.
    bootstrap_step_types()
    for name in StepTypeName:
        assert callable(getattr(get_step_type(name), "needs_context_forge", None)), name


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        (_step(StepTypeName.DISPATCH, prompt="hi"), False),
        (_step(StepTypeName.DISPATCH, prompt="hi", artifact="tasks"), True),
        (_step(StepTypeName.COMPACT), False),
        (_step(StepTypeName.BRANCH, op="enter"), True),
        (_step(StepTypeName.DEVLOG), True),
        (_step(StepTypeName.REVIEW, template="code"), True),
        (_step(StepTypeName.SUMMARY), True),
    ],
)
def test_single_steps(step: StepConfig, expected: bool) -> None:
    assert any_step_needs_context_forge([step]) is expected


def test_loop_answers_for_its_body() -> None:
    quiet = _step(StepTypeName.LOOP, max=2, steps=[{"dispatch": {"prompt": "hi"}}])
    needy = _step(
        StepTypeName.LOOP,
        max=2,
        steps=[{"dispatch": {"prompt": "hi"}}, {"review": {"template": "code"}}],
    )
    assert any_step_needs_context_forge([quiet]) is False
    assert any_step_needs_context_forge([needy]) is True


def test_one_needy_step_among_quiet_ones_needs_it() -> None:
    steps = [_step(StepTypeName.DISPATCH, prompt="hi"), _step(StepTypeName.BRANCH, op="enter")]
    assert any_step_needs_context_forge(steps) is True


def test_an_unregistered_step_type_keeps_the_preflight() -> None:
    assert any_step_needs_context_forge([_step("not-a-registered-type")]) is True


def test_no_steps_need_nothing() -> None:
    assert any_step_needs_context_forge([]) is False


@pytest.fixture
def unregistered_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A working directory whose cf pre-flight fails, with project pipelines installed."""
    monkeypatch.chdir(tmp_path)
    pipelines = tmp_path / "project-documents" / "user" / "pipelines"
    pipelines.mkdir(parents=True)
    for name, text in (
        ("no-cf", _DISPATCH_ONLY),
        ("artifact-cf", _DISPATCH_WITH_ARTIFACT),
        ("branch-cf", _WITH_BRANCH),
    ):
        (pipelines / f"{name}.yaml").write_text(text)
    return tmp_path


def _unregistered_cf_client() -> MagicMock:
    client = MagicMock()
    client.get_project.side_effect = ContextForgeError("PROJECT_NOT_FOUND: no registered project")
    return client


async def _run(name: str, params: dict[str, object], runs_dir: Path) -> PipelineResult:
    completed = PipelineResult(
        pipeline_name=name, status=ExecutionStatus.COMPLETED, step_results=[], error=None
    )
    with (
        patch("squadron.cli.commands.run.ContextForgeClient", return_value=_unregistered_cf_client()),
        patch("squadron.cli.commands.run.execute_pipeline", new=AsyncMock(return_value=completed)),
    ):
        return await _run_pipeline(name, params, runs_dir=runs_dir)


@pytest.mark.asyncio
async def test_dispatch_only_pipeline_runs_outside_a_registered_project(
    unregistered_dir: Path,
) -> None:
    result = await _run("no-cf", {}, unregistered_dir)
    assert result.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["artifact-cf", "branch-cf"])
async def test_pipeline_with_a_cf_step_still_fails_the_preflight(
    unregistered_dir: Path, name: str
) -> None:
    with pytest.raises(typer.Exit) as exit_info:
        await _run(name, {"slice": "1"}, unregistered_dir)
    assert exit_info.value.exit_code == 1
