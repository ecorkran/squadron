"""`each → branch enter → implement → branch merge` against a real repo (slice 196 D5-D7).

The implement body is a scripted dispatch; everything git does is real.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.batch_report import ItemOutcome
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.sources import SOURCE_REGISTRY
from squadron.pipeline.steps import register_step_type
from tests.conftest import run_test_git

SLICES = {
    105: ("Batch Foo", "project-documents/user/slices/105-slice.batch-foo.md"),
    106: ("Other Thing", "project-documents/user/slices/106-slice.other-thing.md"),
}


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=i, name=name, design_file=design, status="in_progress")
        for i, (name, design) in SLICES.items()
    ]
    client.list_tasks.return_value = [TaskEntry(index=i, files=[]) for i in SLICES]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice="105", name="squadron"
    )
    client.get_config.return_value = ""
    client.list_worktrees.return_value = []
    return client


async def _run_batch(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    runs_dir: Path,
    implement: dict[str, tuple[bool, bool]],
):
    """Run the composition. ``implement`` maps slice index -> (writes a file, succeeds).

    An implement that succeeds also commits its file, as the real agent would.
    """

    async def source(*_: object) -> list[dict[str, object]]:
        return [{"index": str(i), "name": SLICES[i][0]} for i in SLICES]

    monkeypatch.setitem(SOURCE_REGISTRY, ("test", "slices"), source)

    async def implement_exec(ctx: ActionContext) -> ActionResult:
        index = int(str(ctx.params["index"]))
        writes, succeeds = implement[index]
        if writes:
            (repo / f"work{index}.txt").write_text("work\n")
        if writes and succeeds:
            run_test_git(repo, "add", "-A")
            run_test_git(repo, "commit", "-q", "-m", f"feat: implement slice {index}")
        return ActionResult(
            success=succeeds,
            action_type="dispatch",
            outputs={},
            error=None if succeeds else "implement failed",
        )

    dispatch = MagicMock()
    dispatch.execute = implement_exec
    body = MagicMock()
    body.expand.return_value = [("dispatch", {"index": "{slice.index}"})]
    register_step_type("_test_implement", body)

    definition = PipelineDefinition(
        name="branch-batch",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="each",
                name="slices",
                config={
                    "source": "test.slices()",
                    "as": "slice",
                    "on_item_failure": "continue",
                    "steps": [
                        {"branch": {"op": "enter", "slice": "{slice.index}"}},
                        {"_test_implement": {}},
                        {"branch": {"op": "merge", "slice": "{slice.index}"}},
                    ],
                },
            )
        ],
    )
    return await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(repo),
        runs_dir=runs_dir,
        _action_registry={"dispatch": dispatch, "branch": BranchAction()},
    )


def _branch(repo: Path) -> str:
    return run_test_git(repo, "branch", "--show-current").strip()


@pytest.mark.asyncio
async def test_failed_item_is_flagged_and_the_next_item_starts_from_the_target(
    temp_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    result = await _run_batch(
        monkeypatch,
        temp_git_repo,
        tmp_path / "runs",
        implement={105: (True, False), 106: (True, True)},
    )

    assert result.status == ExecutionStatus.COMPLETED
    report = result.step_results[0].batch_report
    assert report is not None
    assert [(r.index, r.outcome) for r in report.records] == [
        ("105", ItemOutcome.FLAGGED),
        ("106", ItemOutcome.PASSED),
    ]

    # Item 1 stays unmerged on its own branch with its leftovers committed there.
    flagged_log = run_test_git(temp_git_repo, "log", "105-slice.batch-foo", "--format=%s")
    assert "chore: preserve uncommitted work on flagged slice 105" in flagged_log
    on_flagged = run_test_git(temp_git_repo, "ls-tree", "-r", "--name-only", "105-slice.batch-foo")
    assert "work105.txt" in on_flagged

    # Item 2 left it behind (WARNING), branched from the target, and merged.
    assert "left unmerged slice branch 105-slice.batch-foo for main" in caplog.text
    assert _branch(temp_git_repo) == "main"
    main_log = run_test_git(temp_git_repo, "log", "main", "--format=%s")
    assert "merge: slice 106 — Other Thing" in main_log
    assert "merge: slice 105" not in main_log
    on_main = run_test_git(temp_git_repo, "ls-tree", "-r", "--name-only", "main")
    assert "work106.txt" in on_main and "work105.txt" not in on_main


@pytest.mark.asyncio
async def test_a_halting_fault_ends_the_run_but_still_writes_the_report(
    temp_git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    # Item 105 succeeds and merges; then an unrelated file dirties the tree, so item
    # 106's enter hits the dirty-tree guard and ends the run.
    original = BranchAction.execute

    async def dirty_before_second_enter(self: BranchAction, context: ActionContext) -> ActionResult:
        if context.params.get("op") == "enter" and str(context.params.get("slice")) == "106":
            (temp_git_repo / "unrelated.txt").write_text("x\n")
        return await original(self, context)

    monkeypatch.setattr(BranchAction, "execute", dirty_before_second_enter)

    with pytest.raises(GitEnvironmentError, match="working tree not clean: unrelated.txt"):
        await _run_batch(
            monkeypatch,
            temp_git_repo,
            runs_dir,
            implement={105: (True, True), 106: (True, True)},
        )

    reports = list(runs_dir.glob("*.slices.report.md"))
    assert len(reports) == 1
    text = reports[0].read_text()
    assert "105" in text and "106" in text
    assert "run halted before this item finished" in text
