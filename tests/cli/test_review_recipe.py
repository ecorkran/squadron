"""``sq review`` with a recipe name: refusals, dispatch, output and exit codes (slice 434)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import review_recipe as cli_review_recipe
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.models import aliases
from squadron.recipes import recipe_review
from squadron.recipes.recipe_search import PROJECT_RECIPES_DIR
from squadron.review.models import Severity, Verdict
from squadron.review.persistence import SliceInfo
from squadron.review.templates import BuiltinReviewTemplate
from tests.recipes.conftest import RECIPE_ALIASES
from tests.recipes.support import (
    RECIPE_NAME,
    RECIPE_TEXT,
    FakeRecipeSink,
    Scripted,
    ScriptedReviewCall,
    decisions_text,
    defect_repo,
    provider_error,
    review_finding,
    review_result,
)

CLI_REVIEWS = "cli-reviews"
PROJECT = ProjectId(value="github.com/x/fixture", source=ProjectIdSource.REMOTE)
SLICE = SliceInfo(
    index=100,
    name="fixture",
    slice_name="fixture",
    design_file="project-documents/user/slices/100-slice.fixture.md",
    task_files=[],
    arch_file="",
    project="fixture",
)
A1 = review_finding("a1")
B_FAIL = review_finding("b-fail", Severity.FAIL)


def comb(*pairs: tuple[str, str]) -> Scripted:
    return review_result([], Verdict.PASS, raw=decisions_text(*pairs))


def _script(**overrides: list[Scripted]) -> dict[str, list[Scripted]]:
    script: dict[str, list[Scripted]] = {
        "rev-a": [review_result([A1])],
        "rev-b": [review_result([B_FAIL], Verdict.FAIL)],
        "comb-1": [comb(("F1", "KEEP"))],
        "comb-2": [comb(("F1", "KEEP"))],
    }
    script.update(overrides)
    return script


def _write_recipe(repo: Path, name: str, body: str) -> None:
    (repo / PROJECT_RECIPES_DIR / f"{name}.yaml").write_text(f"name: {name}\n{body}", encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_config_paths: dict[str, Path]) -> Path:
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(RECIPE_ALIASES))
    root = defect_repo(tmp_path / "repo")
    (root / PROJECT_RECIPES_DIR).mkdir(parents=True)
    (root / PROJECT_RECIPES_DIR / f"{RECIPE_NAME}.yaml").write_text(RECIPE_TEXT, encoding="utf-8")
    monkeypatch.setattr(recipe_review, "derive_project_id", lambda cwd: PROJECT)
    return root


@pytest.fixture
def sink(monkeypatch: pytest.MonkeyPatch) -> FakeRecipeSink:
    fake = FakeRecipeSink()
    monkeypatch.setattr(cli_review_recipe, "metrology_recipe_sink", lambda cwd: fake)
    return fake


def _scripted(monkeypatch: pytest.MonkeyPatch, **overrides: list[Scripted]) -> ScriptedReviewCall:
    scripted = ScriptedReviewCall(_script(**overrides))
    monkeypatch.setattr(recipe_review, "run_review_with_profile", scripted)
    return scripted


def _code(repo: Path, *args: str, slice_number: str | None = "100") -> Any:
    argv = ["review", "code"]
    if slice_number is not None:
        argv.append(slice_number)
    argv += ["--cwd", str(repo), *args]
    with patch("squadron.cli.commands.review._resolve_slice_number", return_value=SLICE):
        return CliRunner().invoke(app, argv)


def _review_files(repo: Path) -> list[Path]:
    """The suite's autouse fixture sends CLI review saves to ``<tmp>/cli-reviews``."""
    return sorted((repo.parent / CLI_REVIEWS).glob("*.md"))


# --- Task 18: classification, refusals, dispatch ------------------------------------------


def test_unknown_name_exits_1_with_no_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", "no-such-name", "--no-save")
    assert result.exit_code == 1
    assert "no-such-name" in result.output and "Known recipes" in result.output
    assert scripted.calls == []


def test_collision_exits_1_with_no_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_recipe(repo, "rev-a", "reviewers: [rev-b]\n")
    scripted = _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", "rev-a", "--no-save")
    assert result.exit_code == 1 and "is a model alias and a recipe" in result.output
    assert scripted.calls == []


@pytest.mark.parametrize(
    ("name", "body", "args", "member"),
    [
        (RECIPE_NAME, None, ["--diff", "HEAD~1", "--profile", "openrouter"], "profile"),
        (RECIPE_NAME, None, ["--files", "src/*.py"], "needs a diff"),
        ("pooled", "reviewers: [rev-a, rev-b]\npool: true\n", ["--diff", "HEAD~1"], "pool"),
        ("ghost", "reviewers: [rev-a, no-such-member]\n", ["--diff", "HEAD~1"], "no-such-member"),
        (RECIPE_NAME, None, ["--diff", "HEAD~1", "--no-tools"], "tool-less review"),
    ],
)
def test_each_refusal_exits_1_naming_the_recipe(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    body: str | None,
    args: list[str],
    member: str,
) -> None:
    if body is not None:
        _write_recipe(repo, name, body)
    scripted = _scripted(monkeypatch)
    slice_number = None if "--files" in args else "100"
    result = _code(repo, *args, "--model", name, "--no-save", slice_number=slice_number)
    assert result.exit_code == 1
    assert f"recipe '{name}'" in result.output and member in result.output
    assert scripted.calls == []


def test_recipe_name_runs_every_stage_and_saves_one_review_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    scripted = _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME)
    assert result.exit_code == 2, result.output  # FAIL verdict
    assert len(scripted.calls) == 6
    (review_file,) = _review_files(repo)
    ((record, _raw),) = sink.writes
    assert record.review_file == str(review_file) and record.run_id is None


def test_max_builds_the_loop_with_the_recipe_as_reviewer(repo: Path) -> None:
    with (
        patch("squadron.cli.commands.review.run_review_revise", return_value=0) as run,
        patch("squadron.cli.commands.review_revise._require_branch_preconditions"),
    ):
        result = CliRunner().invoke(
            app, ["review", "code", "941", "--max", "1", "--model", RECIPE_NAME]
        )
    assert result.exit_code == 0, result.output
    args = run.call_args.args
    assert (args[0], args[2], args[4]) == (BuiltinReviewTemplate.CODE, RECIPE_NAME, 1)


# --- Task 19: output, exit codes, --no-save -----------------------------------------------


def test_end_to_end_review_file_stage_table_record_and_comb_file_list(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    scripted = _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME, "-v")
    assert result.exit_code == 2, result.output
    assert "## Recipe" in result.output and "comb rev-a > comb-1" in result.output
    (review_file,) = _review_files(repo)
    text = review_file.read_text(encoding="utf-8")
    assert f"aiModel: {RECIPE_NAME}" in text and "aiRecipe: true" in text
    assert len(sink.writes) == 1
    combs = [c for c in scripted.calls if c.alias.startswith("comb")]
    assert combs and all(c.inputs["changed_files"] == "src/app.py" for c in combs)


def test_one_reviewer_fails_and_nothing_kept_exits_1_with_file_and_record(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    _scripted(
        monkeypatch, **{"rev-a": [provider_error("quota exceeded")], "comb-1": [comb(("F1", "DROP"))]}
    )
    result = _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME)
    assert result.exit_code == 1, result.output
    assert "failed stage review rev-a: quota exceeded" in result.output
    assert len(_review_files(repo)) == 1
    ((record, _raw),) = sink.writes
    assert record.verdict is Verdict.UNKNOWN and record.review_file is not None


def test_sink_failure_prints_result_and_record_not_written(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    sink.fail_with = MetrologyStoreError
    _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME)
    assert result.exit_code == 2, result.output
    assert "recipe record: not written" in result.output and "b-fail" in result.output


def test_json_output_has_a_single_model_reviews_keys(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    _scripted(monkeypatch)
    result = _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME, "--output", "json", "--no-save")
    document = json.loads(result.stdout)
    assert set(document) == set(review_result([A1]).to_dict())
    assert document["verdict"] == "FAIL"


def test_no_save_writes_no_file_and_a_record_with_no_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch, sink: FakeRecipeSink
) -> None:
    _scripted(monkeypatch)
    _code(repo, "--diff", "HEAD~1", "--model", RECIPE_NAME, "--no-save")
    assert _review_files(repo) == []
    ((record, _raw),) = sink.writes
    assert record.review_file is None
