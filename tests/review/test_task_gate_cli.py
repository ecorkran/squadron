"""``sq review tasks`` stops on merge steps before any model call (slice 933)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.identity import read_review_frontmatter
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR
from squadron.review.task_gate import TASK_GATE_MODEL
from tests.review.task_gate_support import (
    ARCH,
    CLEAN_BODY,
    DESIGN,
    MODEL,
    OFFENDING_BODY,
    OFFENDING_LINE_NUMBER,
    SINGLE,
    SPLIT,
    cf_client,
    model_result,
    review_names,
    write_project,
)

_RUN_REVIEW = "squadron.cli.commands.review.run_review_with_profile"
_CF = "squadron.cli.commands.review.ContextForgeClient"


def _invoke(root: Path, task_names: list[str], args: list[str]) -> tuple[Result, int]:
    """Run ``sq review`` with cf and the model patched; return the outcome and model calls."""
    with (
        patch(_CF, return_value=cf_client(task_names)),
        patch(_RUN_REVIEW, side_effect=[model_result() for _ in range(3)]) as run_review,
    ):
        outcome = CliRunner().invoke(
            app, [*args, "--model", MODEL, "--profile", "sdk", "--cwd", str(root)]
        )
    return outcome, run_review.call_count


def test_offending_single_file_fails_without_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: OFFENDING_BODY}))

    outcome, model_calls = _invoke(tmp_path, SINGLE, ["review", "tasks", "194"])

    assert outcome.exit_code != 0
    assert "FAIL" in outcome.output
    assert f"line {OFFENDING_LINE_NUMBER}" in outcome.output
    assert model_calls == 0
    assert review_names(tmp_path) == {"194-review.tasks.loop-step-type.md"}
    saved = tmp_path / REVIEWS_DIR / "194-review.tasks.loop-step-type.md"
    assert read_review_frontmatter(saved)["aiModel"] == TASK_GATE_MODEL


def test_offending_second_part_saves_only_that_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies = {SPLIT[0]: CLEAN_BODY, SPLIT[1]: OFFENDING_BODY}
    monkeypatch.chdir(write_project(tmp_path, bodies))

    outcome, model_calls = _invoke(tmp_path, SPLIT, ["review", "tasks", "194"])

    assert outcome.exit_code != 0
    assert model_calls == 0
    assert review_names(tmp_path) == {"194-review.tasks.loop-step-type.part-2.md"}


def test_clean_file_reviews_as_before(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: CLEAN_BODY}))

    outcome, model_calls = _invoke(tmp_path, SINGLE, ["review", "tasks", "194"])

    assert outcome.exit_code == 0, outcome.output
    assert model_calls == 1


def test_explicit_against_form_fails_the_same_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(write_project(tmp_path, {SINGLE[0]: OFFENDING_BODY}))
    task_file = str(TASKS_DIR / SINGLE[0])

    outcome, model_calls = _invoke(
        tmp_path, SINGLE, ["review", "tasks", task_file, "--against", DESIGN, "--no-save"]
    )

    assert outcome.exit_code != 0
    assert f"line {OFFENDING_LINE_NUMBER}" in outcome.output
    assert model_calls == 0


def test_slice_review_is_not_gated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(write_project(tmp_path, {}, design_body=OFFENDING_BODY))
    (tmp_path / ARCH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ARCH).write_text("# arch\n", encoding="utf-8")

    outcome, model_calls = _invoke(tmp_path, SINGLE, ["review", "slice", "194"])

    assert outcome.exit_code == 0, outcome.output
    assert model_calls == 1
