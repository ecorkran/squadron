"""A pipeline ``review: {template: tasks}`` step stops on merge steps (slice 933)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.identity import read_review_frontmatter
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionResult
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR
from squadron.review.task_gate import TASK_GATE_MODEL
from tests.review.task_gate_support import (
    ARCH,
    CLEAN_BODY,
    MODEL,
    OFFENDING_BODY,
    SINGLE,
    SPLIT,
    action_context,
    cf_client,
    model_result,
    review_names,
    write_project,
)

_RUN_REVIEW = "squadron.pipeline.actions.review.run_review_with_profile"


async def _run_step(
    root: Path, task_names: list[str], template: str = "tasks"
) -> tuple[ActionResult, int]:
    with patch(_RUN_REVIEW, side_effect=[model_result() for _ in range(3)]) as run_review:
        result = await ReviewAction().execute(action_context(root, cf_client(task_names), template))
    return result, run_review.call_count


@pytest.mark.asyncio
async def test_offending_single_file_fails_step_without_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: OFFENDING_BODY}))

    result, model_calls = await _run_step(tmp_path, SINGLE)

    assert result.verdict == "FAIL"
    assert model_calls == 0
    saved = tmp_path / REVIEWS_DIR / "194-review.tasks.loop-step-type.md"
    assert read_review_frontmatter(saved)["aiModel"] == TASK_GATE_MODEL


@pytest.mark.asyncio
async def test_offending_part_saves_only_that_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SPLIT[0]: CLEAN_BODY, SPLIT[1]: OFFENDING_BODY}))

    result, model_calls = await _run_step(tmp_path, SPLIT)

    assert result.verdict == "FAIL"
    assert model_calls == 0
    assert review_names(tmp_path) == {"194-review.tasks.loop-step-type.part-2.md"}


@pytest.mark.asyncio
async def test_clean_file_reviews_as_before(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: CLEAN_BODY}))

    result, model_calls = await _run_step(tmp_path, SINGLE)

    assert result.success is True, result.error
    assert model_calls == 1


@pytest.mark.asyncio
async def test_slice_review_step_is_not_gated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(write_project(tmp_path, {}, design_body=OFFENDING_BODY))
    (tmp_path / ARCH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ARCH).write_text("# arch\n", encoding="utf-8")

    result, model_calls = await _run_step(tmp_path, SINGLE, template="slice")

    assert result.success is True, result.error
    assert model_calls == 1


def test_cli_and_pipeline_write_identical_gate_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sync on purpose: the CLI runs its own event loop via asyncio.run.
    bodies = {SPLIT[0]: CLEAN_BODY, SPLIT[1]: OFFENDING_BODY}
    cli_root = write_project(tmp_path / "cli", bodies)
    monkeypatch.chdir(cli_root)
    with (
        patch("squadron.cli.commands.review.ContextForgeClient", return_value=cf_client(SPLIT)),
        patch("squadron.cli.commands.review.run_review_with_profile") as cli_model,
    ):
        CliRunner().invoke(
            app,
            ["review", "tasks", "194", "--model", MODEL, "--profile", "sdk", "--cwd", str(cli_root)],
        )
    pipeline_root = write_project(tmp_path / "pipeline", bodies)
    monkeypatch.chdir(pipeline_root)
    _, pipeline_calls = asyncio.run(_run_step(pipeline_root, SPLIT))

    assert cli_model.call_count == 0
    assert pipeline_calls == 0
    assert review_names(cli_root) == review_names(pipeline_root)
    assert review_names(cli_root) == {"194-review.tasks.loop-step-type.part-2.md"}


@pytest.mark.asyncio
async def test_unreadable_task_file_fails_step_with_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: CLEAN_BODY}))
    task_file = tmp_path / TASKS_DIR / SINGLE[0]
    task_file.write_bytes(b"- [ ] \xff\xfe broken\n")

    result, model_calls = await _run_step(tmp_path, SINGLE)

    assert result.success is False
    assert result.error is not None and SINGLE[0] in result.error
    assert model_calls == 0
