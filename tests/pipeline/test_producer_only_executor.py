"""A producer-only P6 through the real executor (slice 424, Task 9; design D1)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.commit_plan import REVIEW_TEMPLATE_PARAM
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition
from squadron.pipeline.producer_only import producer_only_definition
from squadron.pipeline.state import StateManager
from tests.pipeline.conftest import phase_artifact_cf_client

BUILD_CONTEXT_TEXT = "context for slice 7: implement the tasks"
NON_PRODUCER_ACTIONS = ("review", "checkpoint", "devlog", "branch", "summary", "compact")


class _Recorder:
    """Fake actions that record what each action type received."""

    def __init__(self) -> None:
        self.calls: dict[str, list[ActionContext]] = {}
        self.implement_prompts: list[str] = []

    def _action(self, action_type: str) -> MagicMock:
        async def execute(context: ActionContext) -> ActionResult:
            self.calls.setdefault(action_type, []).append(context)
            outputs: dict[str, object] = {}
            verdict = None
            if action_type == "cf-op" and context.params.get("operation") == "build_context":
                outputs = {"operation": "build_context", "stdout": BUILD_CONTEXT_TEXT}
            if action_type == "dispatch" and context.step_name.startswith("implement"):
                self.implement_prompts.append(DispatchAction()._resolve_prompt(context).text)
            if action_type == "commit":
                outputs = {"committed": True, "sha": "abc1234"}
            if action_type == "review":
                verdict = "PASS"
            return ActionResult(success=True, action_type=action_type, outputs=outputs, verdict=verdict)

        action = MagicMock()
        action.execute = execute
        return action

    def registry(self) -> dict[str, object]:
        types = ("cf-op", "dispatch", "commit", "review", "checkpoint", "devlog", "branch", "summary")
        return {name: self._action(name) for name in types}

    def action_types_run(self) -> set[str]:
        return set(self.calls)


def _producer_only_p6() -> PipelineDefinition:
    return producer_only_definition(load_pipeline("P6")).definition


async def _run(
    definition: PipelineDefinition, tmp_path: Path, recorder: _Recorder
) -> tuple[PipelineResult, str]:
    state_mgr = StateManager(runs_dir=tmp_path)
    run_id = state_mgr.init_run(definition.name, {"slice": "7"})
    result = await execute_pipeline(
        definition,
        {"slice": "7", "model": "sonnet", "merge": "true"},
        resolver=MagicMock(),
        cf_client=phase_artifact_cf_client(7, "7-slice.x.md", "7-tasks.x.md"),
        cwd=str(tmp_path),
        run_id=run_id,
        runs_dir=tmp_path,
        observer=state_mgr.observer(run_id),
        _action_registry=recorder.registry(),
    )
    return result, run_id


@pytest.mark.asyncio
async def test_the_transformed_p6_runs_only_the_implement_step(tmp_path: Path) -> None:
    recorder = _Recorder()
    result, run_id = await _run(_producer_only_p6(), tmp_path, recorder)

    assert result.status is ExecutionStatus.COMPLETED
    completed = StateManager(runs_dir=tmp_path).load(run_id).completed_steps
    assert [step.step_name for step in completed] == ["implement-1"]
    assert recorder.action_types_run() == {"cf-op", "dispatch", "commit"}
    assert not recorder.action_types_run() & set(NON_PRODUCER_ACTIONS)


@pytest.mark.asyncio
async def test_the_dispatch_gets_the_same_prompt_as_in_a_full_run(tmp_path: Path) -> None:
    full_recorder = _Recorder()
    await _run(load_pipeline("P6"), tmp_path / "full", full_recorder)
    only_recorder = _Recorder()
    await _run(_producer_only_p6(), tmp_path / "only", only_recorder)

    assert only_recorder.implement_prompts == full_recorder.implement_prompts == [BUILD_CONTEXT_TEXT]
    only_hash = hashlib.sha256(only_recorder.implement_prompts[0].encode()).hexdigest()
    full_hash = hashlib.sha256(full_recorder.implement_prompts[0].encode()).hexdigest()
    assert only_hash == full_hash


@pytest.mark.asyncio
async def test_the_commit_has_no_review_template(tmp_path: Path) -> None:
    full_recorder = _Recorder()
    await _run(load_pipeline("P6"), tmp_path / "full", full_recorder)
    only_recorder = _Recorder()
    await _run(_producer_only_p6(), tmp_path / "only", only_recorder)

    full_commit = full_recorder.calls["commit"][0].params
    only_commit = only_recorder.calls["commit"][0].params
    assert REVIEW_TEMPLATE_PARAM in full_commit
    assert REVIEW_TEMPLATE_PARAM not in only_commit
    assert only_commit == {k: v for k, v in full_commit.items() if k != REVIEW_TEMPLATE_PARAM}


@pytest.mark.asyncio
async def test_the_transformed_fix_pipeline_commits_once(temp_git_repo: Path, tmp_path: Path) -> None:
    """``fix`` has nothing to strip, so its producer-only run is its ordinary run."""
    from squadron.pipeline.actions.commit import CommitAction
    from squadron.pipeline.actions.fix_context import FixContextAction
    from squadron.pipeline.control_params import RUN_IO_DIR
    from tests.conftest import run_test_git
    from tests.pipeline.test_fix_pipeline import ISSUE_TEXT, SUMMARY, _edit_readme, _FakeAgent, _report

    io_dir = tmp_path / "io"
    io_dir.mkdir()
    (io_dir / "issue.md").write_text(ISSUE_TEXT, encoding="utf-8")
    definition = producer_only_definition(load_pipeline("fix")).definition
    runs_dir = tmp_path / "runs"
    state = StateManager(runs_dir=runs_dir)
    run_id = state.init_run("fix", {})
    before = int(run_test_git(temp_git_repo, "rev-list", "--count", "HEAD").strip())

    result = await execute_pipeline(
        definition,
        {"issue": "301", "issue-file": "issue.md", "commit-to": "current", RUN_IO_DIR: str(io_dir)},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(temp_git_repo),
        run_id=run_id,
        runs_dir=runs_dir,
        observer=state.observer(run_id),
        _action_registry={
            "fix-context": FixContextAction(),
            "dispatch": _FakeAgent(_report(), _edit_readme),
            "commit": CommitAction(),
        },
    )

    assert result.status is ExecutionStatus.COMPLETED, result.error
    assert int(run_test_git(temp_git_repo, "rev-list", "--count", "HEAD").strip()) == before + 1
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%s").strip() == f"fix: {SUMMARY}"
