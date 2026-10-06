"""`implement-plan` end to end over a real temp repo (slice 197 D1, criteria 1-4).

cf, the model dispatches and the reviews are fakes; every git move is real. The fake
dispatch commits on the slice branch as the real agent would, and the fake review
resolves the slice's real diff range, so an implement that commits nothing fails the
review on an empty diff exactly as ``run_review`` does.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.batch_report import BatchReport
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pr.branch import parse_slice_branch
from squadron.review.git_utils import DiffRangeUnresolvedError, resolve_slice_diff_range
from tests.conftest import run_test_git

PLAN = "300"
_SLICES = "project-documents/user/slices"
_REVIEWS = "project-documents/user/reviews"

# index -> (dependencies, has a task file); plan order puts 302 before its dependency.
_PLAN: dict[int, tuple[tuple[int, ...], bool]] = {
    302: ((301,), True),
    301: ((), True),
    303: ((), True),  # its code review never passes
    304: ((303,), True),  # depends on the flagged 303
    305: ((), True),
    306: ((), False),  # no task file
    307: ((308,), True),  # depends on the undesigned 308
    309: ((), True),  # its implement commits nothing
    310: ((), True),  # runs last, so the batch ends on the target
}
_UNDESIGNED = 308
_NEVER_PASSES = 303
_COMMITS_NOTHING = 309


def _design(index: int) -> str:
    return f"{_SLICES}/{index}-slice.s{index}.md"


def _setup_repo(repo: Path) -> None:
    """Designs, passing design and tasks reviews, committed on main."""
    (repo / _SLICES).mkdir(parents=True)
    (repo / _REVIEWS).mkdir(parents=True)
    for index, (dependencies, _) in _PLAN.items():
        (repo / _design(index)).write_text(f"---\ndependencies: {list(dependencies)}\n---\n")
        for template in ("slice", "tasks"):
            review = repo / _REVIEWS / f"{index}-review.{template}.s{index}.md"
            review.write_text("---\nverdict: PASS\n---\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "plan 300 designs")


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=i, name=f"S{i}", design_file=_design(i), status="not_started") for i in _PLAN
    ] + [SliceEntry(index=_UNDESIGNED, name="S308", design_file=None, status="not_started")]
    client.list_tasks.return_value = [
        TaskEntry(index=i, files=[f"{i}-tasks.s{i}.md"], completed=0, total=4)
        for i, (_, tasked) in _PLAN.items()
        if tasked
    ]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice="301", name="squadron"
    )
    client.get_config.return_value = ""
    client.list_worktrees.return_value = []
    return client


def _ok(action_type: str) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type=action_type, outputs={})
    )
    return action


def _slice_on(cwd: str) -> int:
    branch = run_test_git(Path(cwd), "branch", "--show-current").strip()
    index = parse_slice_branch(branch)
    assert index is not None, f"dispatch ran on {branch}, not a slice branch"
    return index


class _Fakes:
    """Scripted dispatch and review; records which slices each ran for."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[int, str]] = []

    async def dispatch(self, ctx: ActionContext) -> ActionResult:
        index = _slice_on(ctx.cwd)
        kind = "revise" if ctx.params.get("feedback") else "implement"
        self.dispatched.append((index, kind))
        if index != _COMMITS_NOTHING:
            work = Path(ctx.cwd) / f"impl{index}.py"
            work.write_text(f"{work.read_text() if work.exists() else ''}# {kind}\n")
            run_test_git(Path(ctx.cwd), "add", "-A")
            run_test_git(Path(ctx.cwd), "commit", "-q", "-m", f"feat: {kind} slice {index}")
        return ActionResult(success=True, action_type="dispatch", outputs={"response": "ok"})

    async def review(self, ctx: ActionContext) -> ActionResult:
        index = _slice_on(ctx.cwd)
        try:
            diff_range = resolve_slice_diff_range(index, ctx.cwd, "main")
        except DiffRangeUnresolvedError as exc:
            # ReviewAction turns this into a failed result the same way.
            return ActionResult(success=False, action_type="review", outputs={}, error=str(exc))
        changed = run_test_git(Path(ctx.cwd), "diff", "--name-only", diff_range).split()
        if not changed:
            return ActionResult(
                success=False,
                action_type="review",
                outputs={},
                error=f"EmptyDiffError: code review resolved diff '{diff_range}' to no changed "
                "files; refusing to run a review with nothing to review",
            )
        verdict = "FAIL" if index == _NEVER_PASSES else "PASS"
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)


async def _run(repo: Path, tmp_path: Path, fakes: _Fakes) -> PipelineResult:
    dispatch = MagicMock()
    dispatch.execute = fakes.dispatch
    review = MagicMock()
    review.execute = fakes.review
    definition = load_pipeline("implement-plan")
    params: dict[str, object] = {k: v for k, v in definition.params.items() if v != "required"}
    params["plan"] = PLAN
    return await execute_pipeline(
        definition,
        params,
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(repo),
        runs_dir=tmp_path / "runs",
        _action_registry={
            "branch": BranchAction(),
            "dispatch": dispatch,
            "review": review,
            "cf-op": _ok("cf-op"),
            "commit": _ok("commit"),
            "devlog": _ok("devlog"),
            "summary": _ok("summary"),
            "checkpoint": _ok("checkpoint"),
        },
    )


@pytest.fixture
def batch(
    temp_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> tuple[Path, PipelineResult, _Fakes]:
    # Sources read designs and reviews relative to the process cwd, as in a real project.
    monkeypatch.chdir(temp_git_repo)
    _setup_repo(temp_git_repo)
    caplog.set_level(logging.WARNING)
    fakes = _Fakes()
    import asyncio

    result = asyncio.run(_run(temp_git_repo, tmp_path, fakes))
    return temp_git_repo, result, fakes


def _report(result: PipelineResult) -> BatchReport:
    report = result.step_results[0].batch_report
    assert report is not None
    return report


def test_items_run_in_dependency_order_and_end_on_the_target(
    batch: tuple[Path, PipelineResult, _Fakes],
) -> None:
    repo, result, _ = batch

    assert result.status == ExecutionStatus.COMPLETED
    report = _report(result)
    assert [r.index for r in report.records] == [
        "301",
        "302",
        "303",
        "304",
        "305",
        "306",
        "307",
        "309",
        "310",
    ]
    assert run_test_git(repo, "branch", "--show-current").strip() == "main"
    merges = run_test_git(repo, "log", "--first-parent", "--format=%s", "main").splitlines()
    assert [m for m in merges if m.startswith("merge: slice")] == [
        "merge: slice 310 — S310",
        "merge: slice 305 — S305",
        "merge: slice 302 — S302",
        "merge: slice 301 — S301",
    ]


def test_each_flag_kind_lands_on_its_item(batch: tuple[Path, PipelineResult, _Fakes]) -> None:
    _, result, _ = batch

    by_index = {r.index: r for r in _report(result).records}
    flags = {
        i: (r.outcome.value, r.flag_kind, r.failed_step, r.reason)
        for i, r in by_index.items()
        if r.flag_kind is not None
    }
    assert flags["303"] == (
        "flagged",
        "review_unresolved",
        "revise-code",
        "loop exhausted at FAIL (accept: review.concerns_or_better)",
    )
    assert by_index["303"].branch == "303-slice.s303"
    assert flags["304"] == ("flagged", "dependency", None, "dependency 303 flagged")
    assert flags["306"] == ("flagged", "not_ready", None, "no task file")
    assert flags["307"] == ("flagged", "dependency", None, "dependency 308 not designed")
    assert flags["309"][1] == "step_failed"
    passed = ("301", "302", "305", "310")
    assert {i: r.outcome.value for i, r in by_index.items() if i in passed} == dict.fromkeys(
        passed, "passed"
    )


def test_flagged_items_never_dispatch(batch: tuple[Path, PipelineResult, _Fakes]) -> None:
    _, _, fakes = batch

    ran = {index for index, _ in fakes.dispatched}
    assert ran.isdisjoint({304, 306, 307})
    # 303 implemented once and was revised for each of its two rounds.
    assert [kind for index, kind in fakes.dispatched if index == 303] == [
        "implement",
        "revise",
        "revise",
    ]


def test_a_flagged_branch_keeps_its_work_unmerged(
    batch: tuple[Path, PipelineResult, _Fakes],
) -> None:
    repo, _, _ = batch

    branch = "303-slice.s303"
    unmerged = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"], cwd=repo, check=False
    )
    assert unmerged.returncode == 1
    assert "impl303.py" in run_test_git(repo, "ls-tree", "-r", "--name-only", branch)
    assert run_test_git(repo, "status", "--porcelain") == ""


def test_an_implement_that_commits_nothing_fails_its_code_review(
    batch: tuple[Path, PipelineResult, _Fakes], caplog: pytest.LogCaptureFixture
) -> None:
    """D12 last row. A branch with no commits has no diff range at all, so the review
    fails resolving it (before its empty-diff check); the item is step_failed, unmerged."""
    repo, result, _ = batch

    record = next(r for r in _report(result).records if r.index == "309")
    assert record.flag_kind == "step_failed"
    assert "Could not resolve diff range for slice 309" in (record.reason or "")
    assert "merge: slice 309" not in run_test_git(repo, "log", "--format=%s", "main")
    assert any(
        r.levelno == logging.WARNING
        and "item 309 FLAGGED: Could not resolve diff range" in r.getMessage()
        for r in caplog.get_records("setup")
    )
