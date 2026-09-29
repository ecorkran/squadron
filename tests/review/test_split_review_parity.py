"""CLI ``sq review tasks`` and a pipeline ``review:`` step agree on split task files.

Issue #153: the pipeline reviewed only part 1 of a split breakdown while the
CLI reviewed every part. Both now name parts through ``review/parts.py``; these
tests pin that they write the same artifacts and that the pipeline's folded
verdict drives a revise loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

import squadron.pipeline.steps.loop  # noqa: F401  # pyright: ignore[reportUnusedImport] — registers the step type
import squadron.pipeline.steps.review  # noqa: F401  # pyright: ignore[reportUnusedImport] — registers the step type
from squadron.cli.app import app
from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.models import ActionContext, PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ResolvedModel
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR

_MODEL = "claude-sonnet-4-20250514"
_DESIGN = "project-documents/user/slices/194-slice.loop-step-type.md"
_TASK_NAMES = [f"194-tasks.loop-step-type-{n}.md" for n in (1, 2, 3)]

_SLICES = [SliceEntry(index=194, name="Loop Step Type", design_file=_DESIGN, status="in_progress")]
_TASKS = [TaskEntry(index=194, files=_TASK_NAMES)]
_PROJECT = ProjectInfo(
    arch_file="project-documents/user/architecture/100-arch.md",
    slice_plan="100-slices.orchestration-v2",
    phase="Phase 6: Implementation",
    slice="194-slice.loop-step-type",
    name="squadron",
)


def _cf_client() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = _SLICES
    client.list_tasks.return_value = _TASKS
    client.get_project.return_value = _PROJECT
    return client


def _result(verdict: Verdict = Verdict.PASS) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[],
        raw_output=f"## Summary\n{verdict}\n",
        template_name="tasks",
        input_files={},
        timestamp=datetime(2026, 9, 29, 12, 0, 0),
        model=_MODEL,
    )


def _project(root: Path, task_names: list[str]) -> Path:
    for doc in (*(str(TASKS_DIR / name) for name in task_names), _DESIGN):
        (root / doc).parent.mkdir(parents=True, exist_ok=True)
        (root / doc).write_text("# doc\n")
    return root


def _review_names(root: Path) -> set[str]:
    return {p.name for p in (root / REVIEWS_DIR).glob("*.md")}


def _run_cli(root: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    monkeypatch.chdir(root)
    with (
        patch("squadron.cli.commands.review.ContextForgeClient", return_value=_cf_client()),
        patch(
            "squadron.cli.commands.review.run_review_with_profile",
            side_effect=[_result() for _ in _TASK_NAMES],
        ),
    ):
        outcome = CliRunner().invoke(
            app,
            ["review", "tasks", "194", "--model", _MODEL, "--profile", "sdk", "--cwd", str(root)],
        )
    assert outcome.exit_code == 0, outcome.output
    return _review_names(root)


def _context(root: Path, cf_client: MagicMock) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(_MODEL, None)
    return ActionContext(
        pipeline_name="review-tasks-only",
        run_id="run-12345678",
        params={"template": "tasks", "slice": 194},
        step_name="review-tasks",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=cf_client,
        cwd=str(root),
    )


async def _run_pipeline_step(root: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    monkeypatch.chdir(root)
    with patch(
        "squadron.pipeline.actions.review.run_review_with_profile",
        side_effect=[_result() for _ in _TASK_NAMES],
    ):
        result = await ReviewAction().execute(_context(root, _cf_client()))
    assert result.success is True, result.error
    return _review_names(root)


def test_cli_and_pipeline_write_identical_part_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sync on purpose: the CLI runs its own event loop via asyncio.run.
    cli_names = _run_cli(_project(tmp_path / "cli", _TASK_NAMES), monkeypatch)
    pipeline_names = asyncio.run(
        _run_pipeline_step(_project(tmp_path / "pipeline", _TASK_NAMES), monkeypatch)
    )

    assert cli_names == pipeline_names
    assert cli_names == {f"194-review.tasks.loop-step-type.part-{n}.md" for n in (1, 2, 3)}
    assert "194-review.tasks.loop-step-type.md" not in cli_names | pipeline_names


@pytest.mark.asyncio
async def test_one_failing_part_runs_a_revise_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """PASS + CONCERNS folds to CONCERNS, so ``skip_if_met`` must not skip the loop."""
    names = _TASK_NAMES[:2]
    monkeypatch.chdir(_project(tmp_path, names))
    cf_client = _cf_client()
    cf_client.list_tasks.return_value = [TaskEntry(index=194, files=names)]
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(_MODEL, None)
    review: dict[str, object] = {"template": "tasks", "slice": 194}
    pipeline = PipelineDefinition(
        name="tasks-plan-split",
        description="test",
        params={},
        steps=[
            StepConfig(step_type="review", name="review-tasks", config=review),
            StepConfig(
                step_type="loop",
                name="revise",
                config={
                    "max": 2,
                    "until": "review.pass",
                    "skip_if_met": True,
                    "steps": [{"review": review}],
                },
            ),
        ],
    )
    verdicts = [Verdict.PASS, Verdict.CONCERNS, Verdict.PASS, Verdict.PASS]

    with (
        patch(
            "squadron.pipeline.actions.review.run_review_with_profile",
            side_effect=[_result(v) for v in verdicts],
        ) as run_review,
        caplog.at_level(logging.INFO),
    ):
        result = await execute_pipeline(
            pipeline,
            {"_project": "squadron"},
            resolver=resolver,
            cf_client=cf_client,
            cwd=str(tmp_path),
            _action_registry={"review": ReviewAction()},
        )

    assert "already met" not in caplog.text
    assert result.step_results[1].iteration == 1
    assert run_review.call_count == 4
