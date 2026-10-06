"""Built-in code pipelines enter and merge a slice branch (slice 196 D7, D8)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.data import data_dir
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.review.git_utils import (
    _find_slice_branch,  # pyright: ignore[reportPrivateUsage]
    resolve_slice_diff_range,
)
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client

_CODE_PIPELINES = ("P6", "implement", "P456", "P56")
_SLICE = 105
_BRANCH = "105-slice.stub"
_DESIGN = f"project-documents/user/slices/{_SLICE}-slice.stub.md"


def _shape(name: str) -> list[tuple[str, object]]:
    """The branch, implement and devlog steps of a pipeline, in order, and its summaries."""
    steps = load_pipeline(name).steps
    return [
        (s.step_type, s.config.get("op"))
        for s in steps
        if s.step_type in {"branch", "implement", "devlog"}
    ]


@pytest.mark.parametrize("name", _CODE_PIPELINES)
def test_code_pipelines_enter_implement_devlog_merge_in_order(name: str) -> None:
    assert _shape(name) == [
        ("branch", "enter"),
        ("implement", None),
        ("devlog", None),
        ("branch", "merge"),
    ]


@pytest.mark.parametrize("name", _CODE_PIPELINES)
def test_code_pipelines_validate(name: str) -> None:
    assert validate_pipeline(load_pipeline(name)) == []


def test_p6_summary_runs_after_the_merge() -> None:
    step_types = [s.step_type for s in load_pipeline("P6").steps]
    assert step_types[-1] == "summary"
    assert step_types.index("branch", step_types.index("devlog")) < step_types.index("summary")


@pytest.mark.parametrize("name", _CODE_PIPELINES)
def test_code_pipelines_gate_on_the_revise_loop(name: str) -> None:
    """The code review gate is the revise-code loop, pausing on exhaust (slice 197 D10)."""
    steps = load_pipeline(name).steps
    implement = next(s for s in steps if s.step_type == "implement")
    loop = next(s for s in steps if s.step_type == "loop" and s.name == "revise-code")
    assert implement.config["checkpoint"] == "never"
    assert implement.config["existing"] == "keep"
    assert loop.config["on_exhaust"] == "checkpoint"


@pytest.mark.parametrize("name", ["P456", "P56"])
def test_planning_steps_come_before_the_enter_and_stay_on_the_target(name: str) -> None:
    steps = [s.step_type for s in load_pipeline(name).steps]
    enter = steps.index("branch")
    assert all(t in {"design", "tasks", "loop", "summary", "compact"} for t in steps[:enter])


def test_every_builtin_with_an_implement_step_passes_the_enter_rule() -> None:
    checked = 0
    for path in sorted((data_dir() / "pipelines").glob("*.yaml")):
        definition = load_pipeline(path.stem)
        if any(s.step_type == "implement" for s in definition.steps):
            checked += 1
            assert validate_pipeline(definition) == [], path.name
    assert checked >= len(_CODE_PIPELINES)


# ---------------------------------------------------------------------------
# P6 end to end in a real repo (design criterion 4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p6_runs_on_the_slice_branch_and_ends_merged_on_the_target(
    temp_git_repo: Path,
) -> None:
    repo = temp_git_repo
    (repo / "DEVLOG.md").write_text("# devlog\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "devlog")
    observed: dict[str, object] = {}

    def _ok(action_type: str) -> MagicMock:
        action = MagicMock()
        action.execute = AsyncMock(
            return_value=ActionResult(success=True, action_type=action_type, outputs={})
        )
        return action

    async def implement(_ctx: ActionContext) -> ActionResult:
        observed["branch_during_implement"] = run_test_git(repo, "branch", "--show-current").strip()
        (repo / "feature.py").write_text("print('x')\n")
        run_test_git(repo, "add", "-A")
        run_test_git(repo, "commit", "-q", "-m", "feat: the agent's own commit")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(_ctx: ActionContext) -> ActionResult:
        observed["found_branch"] = _find_slice_branch(_SLICE, str(repo))
        observed["diff_range"] = resolve_slice_diff_range(_SLICE, str(repo), base="main")
        path = repo / f"project-documents/user/reviews/{_SLICE}-review.code.stub.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ndocType: review\nverdict: PASS\n---\n")
        return ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")

    async def devlog(_ctx: ActionContext) -> ActionResult:
        (repo / "DEVLOG.md").write_text("# devlog\n\nentry\n")
        return ActionResult(success=True, action_type="devlog", outputs={})

    dispatch, review_action, devlog_action = MagicMock(), MagicMock(), MagicMock()
    dispatch.execute = AsyncMock(side_effect=implement)
    review_action.execute = AsyncMock(side_effect=review)
    devlog_action.execute = AsyncMock(side_effect=devlog)

    definition = load_pipeline("P6")
    params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}
    params["slice"] = str(_SLICE)
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-5", "sdk")
    cf_client = phase_artifact_cf_client(_SLICE, _DESIGN, "105-tasks.stub.md")
    cf_client.get_config.return_value = ""
    cf_client.list_worktrees.return_value = []

    result = await execute_pipeline(
        definition,
        params,
        resolver=resolver,
        cf_client=cf_client,
        cwd=str(repo),
        _action_registry={
            "cf-op": _ok("cf-op"),
            "dispatch": dispatch,
            "review": review_action,
            "checkpoint": _ok("checkpoint"),
            "commit": CommitAction(),
            "devlog": devlog_action,
            "summary": _ok("summary"),
            "branch": BranchAction(),
        },
    )

    assert result.status == ExecutionStatus.COMPLETED
    # The agent worked on the entered branch, and the review could find it.
    assert observed["branch_during_implement"] == _BRANCH
    assert observed["found_branch"] == _BRANCH
    assert str(observed["diff_range"]).endswith(f"...{_BRANCH}")
    # The run ends on the target with the slice merged and its DEVLOG entry on the branch.
    assert run_test_git(repo, "branch", "--show-current").strip() == "main"
    subjects = run_test_git(repo, "log", "main", "--format=%s").splitlines()
    assert subjects[0] == "merge: slice 105 — stub"
    assert "docs: add DEVLOG entry for slice 105" in subjects
    assert "feat: implement slice 105 (review: PASS)" in subjects
    assert (repo / "feature.py").exists()
    assert run_test_git(repo, "status", "--porcelain") == ""


# ---------------------------------------------------------------------------
# The revise loop pauses on exhaust in every single-slice code pipeline (slice 197
# criterion 12)
# ---------------------------------------------------------------------------

_ROOT_DESIGN = f"{_SLICE}-slice.stub.md"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _CODE_PIPELINES)
async def test_a_non_pass_code_review_pauses_without_merging(
    name: str, temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``loop.max`` must be positive, so one round that stays below the threshold
    exhausts the loop (the design's ``max-revisions=0`` is rejected by the loader)."""
    from squadron.pipeline.state import StateManager

    repo = temp_git_repo
    monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")
    (repo / "DEVLOG.md").write_text("# devlog\n")
    (repo / _ROOT_DESIGN).write_text("# stub design\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "devlog")

    def _ok(action_type: str) -> MagicMock:
        action = MagicMock()
        action.execute = AsyncMock(
            return_value=ActionResult(success=True, action_type=action_type, outputs={})
        )
        return action

    async def dispatch(ctx: ActionContext) -> ActionResult:
        # Design and tasks steps need their artifacts; implement commits code.
        (repo / _ROOT_DESIGN).write_text("# stub design\n")
        tasks = repo / f"project-documents/user/tasks/{_SLICE}-tasks.stub.md"
        tasks.parent.mkdir(parents=True, exist_ok=True)
        tasks.write_text("# stub tasks\n")
        if run_test_git(repo, "branch", "--show-current").strip() == _BRANCH:
            (repo / "feature.py").write_text(f"# {ctx.step_name}\n")
            run_test_git(repo, "add", "-A")
            run_test_git(repo, "commit", "-q", "-m", "feat: the agent's own commit")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(ctx: ActionContext) -> ActionResult:
        verdict = "CONCERNS" if ctx.params.get("template") == "code" else "PASS"
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

    dispatch_action, review_action = MagicMock(), MagicMock()
    dispatch_action.execute = AsyncMock(side_effect=dispatch)
    review_action.execute = AsyncMock(side_effect=review)
    definition = load_pipeline(name)
    params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}
    params.update({"slice": str(_SLICE), "max-revisions": "1", "accept-threshold": "review.pass"})
    runs_dir = tmp_path / "runs"
    run_id = StateManager(runs_dir=runs_dir).init_run(name, params)
    cf_client = phase_artifact_cf_client(_SLICE, _ROOT_DESIGN, f"{_SLICE}-tasks.stub.md")
    cf_client.get_config.return_value = ""
    cf_client.list_worktrees.return_value = []
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-5", "sdk")

    result = await execute_pipeline(
        definition,
        params,
        resolver=resolver,
        cf_client=cf_client,
        cwd=str(repo),
        run_id=run_id,
        runs_dir=runs_dir,
        _action_registry={
            "cf-op": _ok("cf-op"),
            "dispatch": dispatch_action,
            "review": review_action,
            "checkpoint": _ok("checkpoint"),
            "commit": CommitAction(),
            "devlog": _ok("devlog"),
            "summary": _ok("summary"),
            "compact": _ok("compact"),
            "branch": BranchAction(),
        },
    )

    assert result.status == ExecutionStatus.PAUSED
    assert result.paused_at == "revise-code"
    assert run_test_git(repo, "branch", "--show-current").strip() == _BRANCH
    assert "merge: slice" not in run_test_git(repo, "log", "main", "--format=%s")


@pytest.mark.asyncio
async def test_a_second_p6_run_keeps_the_branch_work(temp_git_repo: Path, tmp_path: Path) -> None:
    """slice 197 criterion 12: implement is skipped when the slice branch has work."""
    from squadron.pipeline.actions.dispatch import DispatchAction
    from squadron.pipeline.state import StateManager

    repo = temp_git_repo
    (repo / "DEVLOG.md").write_text("# devlog\n")
    (repo / _ROOT_DESIGN).write_text("# stub design\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "setup")
    # A first run's work, left on the slice branch.
    run_test_git(repo, "checkout", "-q", "-b", _BRANCH)
    (repo / "feature.py").write_text("print('first run')\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "feat: first run")
    run_test_git(repo, "checkout", "-q", "main")

    model_calls: list[str] = []
    real_dispatch = DispatchAction()

    class _Dispatch:
        action_type = "dispatch"

        def validate(self, config: dict[str, object]) -> list[object]:
            return []

        async def execute(self, context: ActionContext) -> ActionResult:
            if context.params.get("existing") == "keep":
                return await real_dispatch.execute(context)
            model_calls.append(context.step_name)
            return ActionResult(success=True, action_type="dispatch", outputs={})

    def _ok(action_type: str) -> MagicMock:
        action = MagicMock()
        action.execute = AsyncMock(
            return_value=ActionResult(success=True, action_type=action_type, outputs={})
        )
        return action

    review = MagicMock()
    review.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")
    )
    definition = load_pipeline("P6")
    params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}
    params["slice"] = str(_SLICE)
    runs_dir = tmp_path / "runs"
    run_id = StateManager(runs_dir=runs_dir).init_run("P6", params)
    cf_client = phase_artifact_cf_client(_SLICE, _ROOT_DESIGN, f"{_SLICE}-tasks.stub.md")
    cf_client.get_config.return_value = ""
    cf_client.list_worktrees.return_value = []

    result = await execute_pipeline(
        definition,
        params,
        resolver=MagicMock(),
        cf_client=cf_client,
        cwd=str(repo),
        run_id=run_id,
        runs_dir=runs_dir,
        _action_registry={
            "cf-op": _ok("cf-op"),
            "dispatch": _Dispatch(),
            "review": review,
            "checkpoint": _ok("checkpoint"),
            "commit": CommitAction(),
            "devlog": _ok("devlog"),
            "summary": _ok("summary"),
            "branch": BranchAction(),
        },
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert model_calls == []  # implement kept the branch's work; the passing review skipped revise
    implement = next(r for r in result.step_results if r.step_type == "implement")
    kept = next(a for a in implement.action_results if a.action_type == "dispatch")
    assert kept.outputs == {"skipped": "branch has work", "ahead": 1}
    assert run_test_git(repo, "log", "-1", "--format=%s", "main").strip() == "merge: slice 105 — stub"
