"""Real run-state, report and pipeline fixtures for run listing tests (slice 199).

Runs are written by ``StateManager`` (``init_run`` and its update methods), reports by
``BatchReport.write``, pipelines as YAML in a temp directory. ``init_run`` prunes old
terminal runs of the same pipeline, so a test that needs many terminal runs of one
pipeline calls ``init_run`` for all of them before finalizing any (``begin`` / ``end``).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from squadron.pipeline.batch_report import BatchItemRecord, BatchReport, FlagKind, ItemOutcome
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.state import StateManager

EACH_STEP = "slices"
SECOND_EACH_STEP = "fixes"
#: Step names a step pipeline's definition gets from its YAML below.
STEP_NAMES = ["design-0", "tasks-1", "devlog-2"]

_STEP_YAML = """\
name: {name}
description: step pipeline {name}
steps:
  - design: {{ phase: 4 }}
  - tasks: {{ phase: 5 }}
  - devlog: {{ mode: auto }}
"""

_EACH_YAML = """\
  - each:
      name: {each}
      source: cf.slices("{{plan}}")
      as: slice
      steps:
        - devlog: {{ mode: auto }}
"""


def write_step_pipeline(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(_STEP_YAML.format(name=name))


def write_batch_pipeline(
    directory: Path, name: str, each_steps: tuple[str, ...] = (EACH_STEP,)
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    text = f"name: {name}\ndescription: batch pipeline {name}\nparams:\n  plan: required\nsteps:\n"
    text += "".join(_EACH_YAML.format(each=each) for each in each_steps)
    (directory / f"{name}.yaml").write_text(text)


def definition_loader(directory: Path) -> Callable[[str], PipelineDefinition]:
    """``load_pipeline`` bound to *directory*; never reads the user or project dirs."""
    return partial(load_pipeline, project_dir=directory, user_dir=directory / "no-user")


class Counting[**P, R]:
    """Wraps a loader and records every call's first argument."""

    def __init__(self, inner: Callable[P, R]) -> None:
        self._inner = inner
        self.calls: list[object] = []

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        self.calls.append(args[0])
        return self._inner(*args, **kwargs)


def _step(name: str, status: ExecutionStatus) -> StepResult:
    return StepResult(step_name=name, step_type="phase", status=status, action_results=[])


def begin(sm: StateManager, pipeline: str, params: dict[str, object] | None = None) -> str:
    """A run in status ``running``."""
    return sm.init_run(pipeline, params if params is not None else {"slice": "199"})


def end(sm: StateManager, run_id: str, status: ExecutionStatus) -> None:
    sm.finalize(run_id, PipelineResult(pipeline_name="", status=status, step_results=[]))


def pause_at(sm: StateManager, run_id: str, step: str, *, done: list[str] | None = None) -> None:
    callback = sm.make_step_callback(run_id)
    for name in done or []:
        callback(_step(name, ExecutionStatus.COMPLETED))
    callback(_step(step, ExecutionStatus.PAUSED))


def fail_at(sm: StateManager, run_id: str, step: str, *, done: list[str] | None = None) -> None:
    callback = sm.make_step_callback(run_id)
    for name in done or []:
        callback(_step(name, ExecutionStatus.COMPLETED))
    callback(_step(step, ExecutionStatus.FAILED))
    end(sm, run_id, ExecutionStatus.FAILED)


def complete_steps(sm: StateManager, run_id: str, steps: list[str]) -> None:
    callback = sm.make_step_callback(run_id)
    for name in steps:
        callback(_step(name, ExecutionStatus.COMPLETED))


def mixed_records() -> list[BatchItemRecord]:
    """3 open items, 1 of them acceptable."""
    return [
        BatchItemRecord(
            "1", "a", ItemOutcome.FLAGGED, reason="x", flag_kind=FlagKind.REVIEW_UNRESOLVED
        ),
        BatchItemRecord("2", "b", ItemOutcome.FLAGGED, reason="x", flag_kind=FlagKind.STEP_FAILED),
        BatchItemRecord("3", "c", ItemOutcome.NOT_RUN, reason="halted"),
        BatchItemRecord("4", "d", ItemOutcome.PASSED),
        BatchItemRecord("5", "e", ItemOutcome.ACCEPTED),
    ]


def write_report(
    sm: StateManager,
    pipeline: str,
    run_id: str,
    records: list[BatchItemRecord],
    step: str = EACH_STEP,
) -> Path:
    report = BatchReport(pipeline, run_id, step, plan="180", records=records)
    report.write(sm.runs_dir)
    return report.json_path(sm.runs_dir)


def completed_batch_run(
    sm: StateManager, pipeline: str, records: list[BatchItemRecord] | None = None
) -> str:
    run_id = begin(sm, pipeline, {"plan": "180"})
    write_report(sm, pipeline, run_id, records if records is not None else mixed_records())
    end(sm, run_id, ExecutionStatus.COMPLETED)
    return run_id
