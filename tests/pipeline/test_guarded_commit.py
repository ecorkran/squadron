"""The guarded ``commit`` step (#292): only named paths, unmoved HEAD, integration target."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.commit_plan import MESSAGE_PARAM, PATHS_PARAM
from squadron.pipeline.control_params import RUN_START_HEAD
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.guarded_commit import GUARDED_PARAM, changed_paths, outside_globs
from squadron.pipeline.models import ActionContext, PipelineDefinition, StepConfig
from squadron.pipeline.prompt_renderer import PromptOnlyUnsupportedError, render_step_instructions
from squadron.pipeline.steps import StepTypeName, bootstrap_step_types, get_step_type
from tests.conftest import run_test_git

PLAN_GLOB = "project-documents/user/architecture/*-slices.*.md"


def _cf(integration_branch: str = "") -> MagicMock:
    client = MagicMock()
    client.get_config.return_value = integration_branch
    return client


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _context(repo: Path, *, globs: list[str], start_head: str | None = None) -> ActionContext:
    params: dict[str, object] = {
        PATHS_PARAM: globs,
        MESSAGE_PARAM: "docs: add slice entry",
        GUARDED_PARAM: True,
        RUN_START_HEAD: start_head if start_head is not None else _head(repo),
    }
    return ActionContext(
        pipeline_name="slice-writing",
        run_id="run-1",
        params=params,
        step_name="commit",
        step_index=1,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(repo),
    )


def _write(repo: Path, relative: str, text: str = "x\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# --- the action ---


@pytest.mark.asyncio
async def test_commits_only_the_files_matching_paths(temp_git_repo: Path) -> None:
    _write(temp_git_repo, "project-documents/user/architecture/120-slices.foo.md")

    result = await CommitAction().execute(_context(temp_git_repo, globs=[PLAN_GLOB]))

    assert result.success, result.error
    assert result.outputs["committed"] is True
    shown = run_test_git(temp_git_repo, "show", "--name-only", "--format=%s", "HEAD")
    assert shown.split() == [
        "docs:",
        "add",
        "slice",
        "entry",
        "project-documents/user/architecture/120-slices.foo.md",
    ]


@pytest.mark.asyncio
async def test_a_changed_file_outside_paths_fails_naming_it_and_commits_nothing(
    temp_git_repo: Path,
) -> None:
    before = _head(temp_git_repo)
    _write(temp_git_repo, "project-documents/user/architecture/120-slices.foo.md")
    _write(temp_git_repo, "notes/stray.md")

    result = await CommitAction().execute(_context(temp_git_repo, globs=[PLAN_GLOB]))

    assert not result.success
    assert "notes/stray.md" in (result.error or "")
    assert _head(temp_git_repo) == before
    assert run_test_git(temp_git_repo, "diff", "--cached", "--name-only") == ""


@pytest.mark.asyncio
async def test_head_moved_since_the_run_started_fails(temp_git_repo: Path) -> None:
    start = _head(temp_git_repo)
    _write(temp_git_repo, "other.md")
    run_test_git(temp_git_repo, "add", "other.md")
    run_test_git(temp_git_repo, "commit", "-m", "agent committed itself")
    _write(temp_git_repo, "project-documents/user/architecture/120-slices.foo.md")

    result = await CommitAction().execute(_context(temp_git_repo, globs=[PLAN_GLOB], start_head=start))

    assert not result.success
    assert "HEAD moved" in (result.error or "")


@pytest.mark.asyncio
async def test_off_the_integration_target_fails(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-b", "elsewhere")
    _write(temp_git_repo, "project-documents/user/architecture/120-slices.foo.md")

    result = await CommitAction().execute(_context(temp_git_repo, globs=[PLAN_GLOB]))

    assert not result.success
    assert "refusing to commit on elsewhere" in (result.error or "")


@pytest.mark.asyncio
async def test_no_changes_succeeds_without_a_commit(temp_git_repo: Path) -> None:
    before = _head(temp_git_repo)

    result = await CommitAction().execute(_context(temp_git_repo, globs=[PLAN_GLOB]))

    assert result.success
    assert result.outputs["committed"] is False
    assert _head(temp_git_repo) == before


@pytest.mark.asyncio
async def test_no_recorded_start_head_fails(temp_git_repo: Path) -> None:
    context = _context(temp_git_repo, globs=[PLAN_GLOB])
    del context.params[RUN_START_HEAD]

    result = await CommitAction().execute(context)

    assert not result.success
    assert "starting commit" in (result.error or "")


# --- status parsing and matching ---


def test_changed_paths_lists_untracked_files_inside_new_directories(temp_git_repo: Path) -> None:
    _write(temp_git_repo, "a/b/new.md")

    assert changed_paths(str(temp_git_repo)) == ["a/b/new.md"]


def test_changed_paths_lists_both_sides_of_a_rename(temp_git_repo: Path) -> None:
    _write(temp_git_repo, "old name.md")
    run_test_git(temp_git_repo, "add", "old name.md")
    run_test_git(temp_git_repo, "commit", "-m", "add")
    run_test_git(temp_git_repo, "mv", "old name.md", "new name.md")

    assert sorted(changed_paths(str(temp_git_repo))) == ["new name.md", "old name.md"]


def test_outside_globs_star_crosses_directories() -> None:
    assert outside_globs(["docs/a/b.md", "src/x.py"], ["docs/*.md"]) == ["src/x.py"]


# --- the step type ---


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type=StepTypeName.COMMIT, name="commit", config=config)


@pytest.mark.parametrize(
    ("config", "field"),
    [
        ({MESSAGE_PARAM: "m"}, PATHS_PARAM),
        ({PATHS_PARAM: [], MESSAGE_PARAM: "m"}, PATHS_PARAM),
        ({PATHS_PARAM: "docs/*.md", MESSAGE_PARAM: "m"}, PATHS_PARAM),
        ({PATHS_PARAM: ["/abs/*.md"], MESSAGE_PARAM: "m"}, PATHS_PARAM),
        ({PATHS_PARAM: ["../up/*.md"], MESSAGE_PARAM: "m"}, PATHS_PARAM),
        ({PATHS_PARAM: ["docs/*.md"]}, MESSAGE_PARAM),
        ({PATHS_PARAM: ["docs/*.md"], MESSAGE_PARAM: "  "}, MESSAGE_PARAM),
    ],
)
def test_step_validation_rejects_bad_config(config: dict[str, object], field: str) -> None:
    bootstrap_step_types()

    errors = get_step_type(StepTypeName.COMMIT).validate(_step(config))

    assert [error.field for error in errors] == [field]


def test_step_expands_to_one_guarded_commit_action() -> None:
    bootstrap_step_types()

    actions = get_step_type(StepTypeName.COMMIT).expand(
        _step({PATHS_PARAM: ["docs/*.md"], MESSAGE_PARAM: "m"})
    )

    assert actions == [
        ("commit", {PATHS_PARAM: ["docs/*.md"], MESSAGE_PARAM: "m", GUARDED_PARAM: True})
    ]


def test_prompt_only_refuses_the_commit_step() -> None:
    bootstrap_step_types()
    step = _step({PATHS_PARAM: ["docs/*.md"], MESSAGE_PARAM: "m"})

    with pytest.raises(PromptOnlyUnsupportedError, match="sq run"):
        render_step_instructions(
            step, step_index=0, total_steps=1, params={}, resolver=MagicMock(), run_id="run-1"
        )


# --- through the executor ---


@pytest.mark.asyncio
async def test_a_run_param_in_a_glob_resolves_and_the_run_commits(temp_git_repo: Path) -> None:
    definition = PipelineDefinition(
        name="slice-writing",
        description="test",
        params={"requests-index": "required"},
        steps=[
            _step(
                {
                    PATHS_PARAM: ["project-documents/user/architecture/{requests-index}-slices.*.md"],
                    MESSAGE_PARAM: "docs: add slice entry",
                }
            )
        ],
    )
    _write(temp_git_repo, "project-documents/user/architecture/120-slices.foo.md")

    result = await execute_pipeline(
        definition,
        {"requests-index": "120"},
        resolver=MagicMock(),  # type: ignore[arg-type]
        cf_client=_cf(),  # type: ignore[arg-type]
        cwd=str(temp_git_repo),
    )

    assert result.status is ExecutionStatus.COMPLETED, result.error
    assert run_test_git(temp_git_repo, "status", "--porcelain") == ""
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%s") == "docs: add slice entry\n"
