"""A batch run on disk for item resume tests: a temp repo, run state, report.json and cf.

Plan 400 has slices 401 (flagged review_unresolved, with work on its branch), 402
(depends on 401, flagged dependency), 403 (passed) and 404 (not_run).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    FlagKind,
    ItemOutcome,
    ItemRerun,
)
from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.state import StateManager
from squadron.pr.branch import parse_slice_branch
from tests.conftest import run_test_git

PLAN = "400"
PIPELINE = "implement-plan"
_SLICES = "project-documents/user/slices"
_REVIEWS = "project-documents/user/reviews"
_DEPENDENCIES: dict[int, list[int]] = {401: [], 402: [401], 403: [], 404: []}


def design(index: int) -> str:
    return f"{_SLICES}/{index}-slice.s{index}.md"


def branch(index: int) -> str:
    return f"{index}-slice.s{index}"


def commit_file(repo: Path, name: str, text: str = "x\n", message: str | None = None) -> None:
    (repo / name).write_text(text)
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", message or f"add {name}")


@dataclass
class Project:
    repo: Path
    runs_dir: Path
    run_id: str
    cf: MagicMock
    status: dict[int, str] = field(default_factory=lambda: {})

    @property
    def report_path(self) -> Path:
        return self.runs_dir / f"{self.run_id}.slices.report.json"

    def report(self) -> BatchReport:
        return BatchReport.load(self.report_path)

    def record(self, index: str) -> BatchItemRecord:
        return next(r for r in self.report().records if r.index == index)

    def current_branch(self) -> str:
        return run_test_git(self.repo, "branch", "--show-current").strip()


def make_project(repo: Path, runs_dir: Path) -> Project:
    """Designs and passing reviews on main; 401's branch has one implement commit."""
    (repo / _SLICES).mkdir(parents=True)
    (repo / _REVIEWS).mkdir(parents=True)
    for index, dependencies in _DEPENDENCIES.items():
        (repo / design(index)).write_text(f"---\ndependencies: {dependencies}\n---\n")
        for template in ("slice", "tasks"):
            review = repo / _REVIEWS / f"{index}-review.{template}.s{index}.md"
            review.write_text("---\nverdict: PASS\n---\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "plan 400 designs")
    run_test_git(repo, "checkout", "-q", "-b", branch(401))
    commit_file(repo, "impl401.py", "# implement\n", "feat: implement slice 401")
    run_test_git(repo, "checkout", "-q", "main")

    status = {index: "not_started" for index in _DEPENDENCIES}
    status[403] = "complete"
    cf = MagicMock()
    cf.list_slices.side_effect = lambda *_: [
        SliceEntry(index=i, name=f"S{i}", design_file=design(i), status=status[i])
        for i in _DEPENDENCIES
    ]
    cf.list_tasks.return_value = [
        TaskEntry(index=i, files=[f"{i}-tasks.s{i}.md"], completed=0, total=4) for i in _DEPENDENCIES
    ]
    cf.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice="401", name="squadron"
    )
    cf.get_config.return_value = ""
    cf.list_worktrees.return_value = []

    state_manager = StateManager(runs_dir=runs_dir)
    params = {k: v for k, v in load_pipeline(PIPELINE).params.items() if v != "required"}
    params.update({"plan": PLAN, "model": "haiku"})
    run_id = state_manager.init_run(PIPELINE, params)
    report = BatchReport(PIPELINE, run_id, "slices", plan=PLAN)
    report.records = [
        BatchItemRecord(
            "401",
            "S401",
            ItemOutcome.FLAGGED,
            reason="loop exhausted at FAIL (accept: review.concerns_or_better)",
            final_verdict="FAIL",
            flag_kind=FlagKind.REVIEW_UNRESOLVED,
            failed_step="revise-code",
            branch=branch(401),
        ),
        BatchItemRecord(
            "402",
            "S402",
            ItemOutcome.FLAGGED,
            reason="dependency 401 flagged",
            flag_kind=FlagKind.DEPENDENCY,
        ),
        BatchItemRecord("403", "S403", ItemOutcome.PASSED),
        BatchItemRecord("404", "S404", ItemOutcome.NOT_RUN, reason="run halted"),
    ]
    report.write(runs_dir)
    return Project(repo, runs_dir, run_id, cf, status)


def ok_action(action_type: str) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type=action_type, outputs={})
    )
    return action


@dataclass
class BodyFakes:
    """Scripted dispatch and code review for the item body; records what ran."""

    verdicts: list[str]
    dispatch_prompts: list[tuple[str, dict[str, object]]] = field(default_factory=lambda: [])
    reviews: int = 0

    async def dispatch(self, ctx: ActionContext) -> ActionResult:
        from squadron.pipeline.actions.dispatch import (
            DispatchAction,
            _kept_outputs,  # pyright: ignore[reportPrivateUsage]
        )

        if ctx.params.get("existing") == "keep":
            # The real keep check (it reads the branch's work); "dispatch" only without work.
            kept = _kept_outputs(ctx)  # pyright: ignore[reportPrivateUsage]
            if kept is not None:
                return ActionResult(success=True, action_type="dispatch", outputs=kept)
        kind = "revise" if ctx.params.get("feedback") else "implement"
        prompt = DispatchAction._apply_override(ctx, f"{kind} prompt")  # pyright: ignore[reportPrivateUsage]
        self.dispatch_prompts.append((kind, {"prompt": prompt}))
        index = parse_slice_branch(run_test_git(Path(ctx.cwd), "branch", "--show-current").strip())
        work = Path(ctx.cwd) / f"impl{index}.py"
        work.write_text(f"{work.read_text() if work.exists() else ''}# {kind}\n")
        run_test_git(Path(ctx.cwd), "add", "-A")
        run_test_git(Path(ctx.cwd), "commit", "-q", "-m", f"feat: {kind} slice {index}")
        return ActionResult(success=True, action_type="dispatch", outputs={"response": "ok"})

    async def review(self, ctx: ActionContext) -> ActionResult:
        verdict = self.verdicts[min(self.reviews, len(self.verdicts) - 1)]
        self.reviews += 1
        return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)


def body_runner(project: Project, fakes: BodyFakes):  # type: ignore[no-untyped-def]
    """Runs the item body the way ``sq run`` does: the run's pipeline from its ``each``."""

    async def run(pipeline: str, params: dict[str, object], rerun: ItemRerun) -> object:
        dispatch, review = MagicMock(), MagicMock()
        dispatch.execute = fakes.dispatch
        review.execute = fakes.review
        return await execute_pipeline(
            load_pipeline(pipeline),
            params,
            resolver=MagicMock(),
            cf_client=project.cf,
            cwd=str(project.repo),
            run_id=project.run_id,
            runs_dir=project.runs_dir,
            item_rerun=rerun,
            _action_registry={
                "branch": BranchAction(),
                "dispatch": dispatch,
                "review": review,
                "cf-op": ok_action("cf-op"),
                "commit": ok_action("commit"),
                "devlog": ok_action("devlog"),
                "summary": ok_action("summary"),
                "checkpoint": ok_action("checkpoint"),
            },
        )

    return run


async def resume(
    project: Project,
    index: str,
    decision: object,
    fakes: BodyFakes,
    *,
    instructions: str | None = None,
    overrides: dict[str, str] | None = None,
):  # type: ignore[no-untyped-def]
    from squadron.pipeline.item_resume import ResumeRequest, resume_item

    return await resume_item(
        ResumeRequest(
            run_id=project.run_id,
            index=index,
            decision=decision,  # type: ignore[arg-type]
            instructions=instructions,
            param_overrides=overrides or {},
        ),
        cwd=str(project.repo),
        cf_client=project.cf,
        state_manager=StateManager(runs_dir=project.runs_dir),
        run_body=body_runner(project, fakes),
    )
