"""A planning loop collapses its own commits on completion, through the real executor (slice 202).

The loop, the commit action, run state and git are real; the dispatch and review actions
are scripted. History is what each test asserts on, plus the observable log line.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401  # pyright: ignore[reportUnusedImport] — registers the step type
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.control_params import ACCEPT_DECISION
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import register_step_type
from tests.conftest import run_test_git
from tests.pipeline.conftest import phase_artifact_cf_client

SLICE = 105
DESIGN = "project-documents/user/slices/105-slice.stub.md"
REVIEW = "project-documents/user/reviews/105-review.slice.stub.md"
LOOP_NAME = "design-loop"
COLLAPSE_LOGGER = "squadron.pipeline.loop_collapse"


@dataclass
class Review:
    """One scripted review: its verdict, and whether it stops the run at a checkpoint."""

    verdict: str
    pause: bool = False


@dataclass
class Script:
    """What the fake actions do, shared by every execution of one test's run."""

    repo: Path
    reviews: list[Review]
    revisions: int = 0
    review_calls: int = 0
    log: list[str] = field(default_factory=lambda: [])

    def _write(self, relative: str, text: str) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    async def dispatch(self, _ctx: ActionContext) -> ActionResult:
        self.revisions += 1
        self._write(DESIGN, f"design v{self.revisions}\n")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    async def review(self, _ctx: ActionContext) -> ActionResult:
        scripted = self.reviews[self.review_calls]
        self.review_calls += 1
        self._write(REVIEW, f"---\ndocType: review\nverdict: {scripted.verdict}\n---\n")
        outputs: dict[str, object] = {"checkpoint": "paused"} if scripted.pause else {}
        return ActionResult(
            success=True, action_type="review", outputs=outputs, verdict=scripted.verdict
        )


def _action(effect: object) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=effect)
    return action


def _step_type(actions: list[tuple[str, dict[str, object]]]) -> MagicMock:
    step_type = MagicMock()
    step_type.expand.return_value = actions
    return step_type


def _commit_params() -> dict[str, object]:
    return {"commit_subject": "design", "slice": str(SLICE), "review_template": "slice"}


def _pipeline(
    tag: str, *, max_rounds: int, phase: bool = True, leading_review: bool = False, **loop_extra: object
) -> PipelineDefinition:
    review_actions: list[tuple[str, dict[str, object]]] = [
        ("review", {"template": "slice", "slice": str(SLICE)})
    ]
    register_step_type(f"_cx_dispatch_{tag}", _step_type([("dispatch", {})]))
    register_step_type(f"_cx_review_{tag}", _step_type(review_actions))
    register_step_type(f"_cx_phase_{tag}", _step_type([("dispatch", {}), ("commit", _commit_params())]))
    steps: list[StepConfig] = []
    if phase:
        steps.append(StepConfig(step_type=f"_cx_phase_{tag}", name="design", config={}))
    if leading_review:
        steps.append(StepConfig(step_type=f"_cx_review_{tag}", name="review", config={}))
    steps.append(
        StepConfig(
            step_type="loop",
            name=LOOP_NAME,
            config={
                "max": max_rounds,
                "until": "review.pass",
                "commit_each_iteration": True,
                "steps": [{f"_cx_dispatch_{tag}": {}}, {f"_cx_review_{tag}": {}}],
                **loop_extra,
            },
        )
    )
    return PipelineDefinition(name=f"cx-{tag}", description="test", params={}, steps=steps)


@dataclass
class Run:
    """One run's state on disk, so a later execution can resume it."""

    pipeline: PipelineDefinition
    script: Script
    runs_dir: Path
    run_id: str
    state: StateManager


def _start(pipeline: PipelineDefinition, repo: Path, reviews: list[Review], runs_dir: Path) -> Run:
    state = StateManager(runs_dir=runs_dir)
    run_id = state.init_run(pipeline.name, {"slice": str(SLICE)})
    return Run(pipeline, Script(repo, reviews), runs_dir, run_id, state)


async def _execute(
    run: Run, *, resume: bool = False, params: dict[str, object] | None = None
) -> PipelineResult:
    cf_client = phase_artifact_cf_client(SLICE, DESIGN, "105-tasks.stub.md")
    cf_client.get_config.return_value = ""
    resume_args: dict[str, object] = {}
    if resume:
        resume_args = {
            "start_from": LOOP_NAME,
            "start_from_iteration": run.state.resume_iteration_for(run.run_id, LOOP_NAME),
        }
    return await execute_pipeline(
        run.pipeline,
        {"slice": str(SLICE), **(params or {})},
        resolver=MagicMock(),
        cf_client=cf_client,
        cwd=str(run.script.repo),
        run_id=run.run_id,
        runs_dir=run.runs_dir,
        observer=run.state.observer(run.run_id),
        _action_registry={
            "dispatch": _action(run.script.dispatch),
            "review": _action(run.script.review),
            "commit": CommitAction(),
        },
        **resume_args,  # type: ignore[arg-type]
    )


def _subjects(repo: Path) -> list[str]:
    return run_test_git(repo, "log", "--format=%s", "--reverse").splitlines()


def _collapse_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == COLLAPSE_LOGGER]


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs"


# ---------------------------------------------------------------------------
# Completion collapses the phase commit and the rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_commit_and_two_rounds_collapse_into_one_commit(
    temp_git_repo: Path, runs_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run = _start(
        _pipeline("two", max_rounds=3),
        temp_git_repo,
        [Review("CONCERNS"), Review("PASS")],
        runs_dir,
    )

    with caplog.at_level(logging.INFO, logger=COLLAPSE_LOGGER):
        result = await _execute(run)

    assert result.status == ExecutionStatus.COMPLETED
    assert _subjects(temp_git_repo) == ["init", "docs: add slice 105 design (review: PASS)"]
    ledger = result.step_results[-1].loop_commits
    assert ledger is not None and len(ledger.commits) == 3
    head = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()
    backup = f"refs/squadron/pre-collapse/{head}"
    tree = run_test_git(temp_git_repo, "rev-parse", "HEAD^{tree}")
    assert run_test_git(temp_git_repo, "rev-parse", f"{backup}^{{tree}}") == tree
    assert [r.levelno for r in _collapse_records(caplog)] == [logging.INFO]
    assert "collapsed 3 commits" in _collapse_records(caplog)[0].getMessage()


@pytest.mark.asyncio
async def test_a_single_round_commit_leaves_history_and_logs_nothing(
    temp_git_repo: Path, runs_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run = _start(
        _pipeline("single", max_rounds=2, phase=False), temp_git_repo, [Review("PASS")], runs_dir
    )

    with caplog.at_level(logging.DEBUG, logger=COLLAPSE_LOGGER):
        result = await _execute(run)

    assert result.status == ExecutionStatus.COMPLETED
    assert len(_subjects(temp_git_repo)) == 2  # init and the one round commit
    assert _collapse_records(caplog) == []


@pytest.mark.asyncio
async def test_a_loop_skipped_because_its_condition_is_met_leaves_history(
    temp_git_repo: Path, runs_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run = _start(
        _pipeline("skip", max_rounds=2, leading_review=True, skip_if_met=True),
        temp_git_repo,
        [Review("PASS")],
        runs_dir,
    )

    with caplog.at_level(logging.DEBUG, logger=COLLAPSE_LOGGER):
        result = await _execute(run)

    assert result.step_results[-1].iteration == 0
    assert _subjects(temp_git_repo) == ["init", "docs: add slice 105 design"]
    assert _collapse_records(caplog) == []


# ---------------------------------------------------------------------------
# Exhaustion: collapse only when the loop completes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exhaustion_accepted_by_accept_if_collapses(temp_git_repo: Path, runs_dir: Path) -> None:
    run = _start(
        _pipeline("accept", max_rounds=2, accept_if="review.concerns_or_better"),
        temp_git_repo,
        [Review("CONCERNS"), Review("CONCERNS")],
        runs_dir,
    )

    result = await _execute(run)

    assert result.step_results[-1].accepted is True
    assert _subjects(temp_git_repo) == ["init", "docs: add slice 105 design (review: CONCERNS)"]


@pytest.mark.asyncio
async def test_a_failed_loop_never_collapses(temp_git_repo: Path, runs_dir: Path) -> None:
    run = _start(
        _pipeline("failed", max_rounds=2, on_exhaust="fail"),
        temp_git_repo,
        [Review("FAIL"), Review("FAIL")],
        runs_dir,
    )

    result = await _execute(run)

    assert result.status == ExecutionStatus.FAILED
    assert len(_subjects(temp_git_repo)) == 4  # init, the phase commit, two rounds


# ---------------------------------------------------------------------------
# A pause carries the ledger across the resume
# ---------------------------------------------------------------------------

_PAUSE_AT_ROUND_TWO = [Review("CONCERNS"), Review("CONCERNS", pause=True), Review("PASS")]


async def _paused_run(repo: Path, runs_dir: Path, tag: str) -> Run:
    run = _start(_pipeline(tag, max_rounds=4), repo, list(_PAUSE_AT_ROUND_TWO), runs_dir)
    paused = await _execute(run)
    assert paused.status == ExecutionStatus.PAUSED
    assert len(_subjects(repo)) == 3  # init, the phase commit, round 1
    return run


@pytest.mark.asyncio
async def test_resuming_for_more_rounds_collapses_across_both_executions(
    temp_git_repo: Path, runs_dir: Path
) -> None:
    run = await _paused_run(temp_git_repo, runs_dir, "resume")

    resumed = await _execute(run, resume=True)

    assert resumed.status == ExecutionStatus.COMPLETED
    assert _subjects(temp_git_repo) == ["init", "docs: add slice 105 design (review: PASS)"]


@pytest.mark.asyncio
async def test_resuming_with_decision_accept_collapses_what_was_committed(
    temp_git_repo: Path, runs_dir: Path
) -> None:
    run = await _paused_run(temp_git_repo, runs_dir, "accept-resume")

    resumed = await _execute(run, resume=True, params={ACCEPT_DECISION: True})

    assert resumed.step_results[-1].accepted is True
    assert _subjects(temp_git_repo) == ["init", "docs: add slice 105 design (review: CONCERNS)"]


@pytest.mark.asyncio
async def test_an_operator_commit_during_the_pause_leaves_history_and_warns(
    temp_git_repo: Path, runs_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run = await _paused_run(temp_git_repo, runs_dir, "operator")
    (temp_git_repo / "operator.md").write_text("mine\n")
    run_test_git(temp_git_repo, "add", "operator.md")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "operator work")

    with caplog.at_level(logging.INFO, logger=COLLAPSE_LOGGER):
        resumed = await _execute(run, resume=True)

    assert resumed.status == ExecutionStatus.COMPLETED
    subjects = _subjects(temp_git_repo)
    assert len(subjects) == 5  # init, phase, round 1, operator, round 2
    assert "operator work" in subjects
    records = _collapse_records(caplog)
    assert [r.levelno for r in records] == [logging.WARNING]
    assert "uncollapsed" in records[0].getMessage()


@pytest.mark.asyncio
async def test_a_state_record_from_before_ledgers_existed_refuses_to_collapse(
    temp_git_repo: Path, runs_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run = await _paused_run(temp_git_repo, runs_dir, "pre-slice")
    state_file = runs_dir / f"{run.run_id}.json"
    state = json.loads(state_file.read_text())
    for step in state["completed_steps"]:
        step.pop("loop_commits", None)
    state_file.write_text(json.dumps(state))

    with caplog.at_level(logging.INFO, logger=COLLAPSE_LOGGER):
        resumed = await _execute(run, resume=True)

    assert resumed.status == ExecutionStatus.COMPLETED
    assert len(_subjects(temp_git_repo)) == 4  # init, phase, round 1, round 2
    assert [r.levelno for r in _collapse_records(caplog)] == [logging.WARNING]


# ---------------------------------------------------------------------------
# A rerun, and a loop that never collapses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_rerun_collapses_only_its_own_commits(temp_git_repo: Path, runs_dir: Path) -> None:
    first = _start(
        _pipeline("flagged", max_rounds=2, phase=False, on_exhaust="fail"),
        temp_git_repo,
        [Review("FAIL"), Review("FAIL")],
        runs_dir,
    )
    assert (await _execute(first)).status == ExecutionStatus.FAILED
    flagged_attempt = _subjects(temp_git_repo)[1:]
    assert len(flagged_attempt) == 2

    rerun = _start(
        _pipeline("rerun", max_rounds=2, phase=False),
        temp_git_repo,
        [Review("FAIL"), Review("PASS")],
        runs_dir,
    )
    assert (await _execute(rerun)).status == ExecutionStatus.COMPLETED

    subjects = _subjects(temp_git_repo)
    assert subjects[:3] == ["init", *flagged_attempt]
    assert len(subjects) == 4  # the rerun's two rounds became one


@pytest.mark.asyncio
async def test_a_code_loop_never_collapses(temp_git_repo: Path, runs_dir: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "105-slice.stub")
    register_step_type("_cx_code_dispatch", _step_type([("dispatch", {})]))
    register_step_type(
        "_cx_code_review",
        _step_type([("review", {"template": "code", "slice": str(SLICE)})]),
    )
    pipeline = PipelineDefinition(
        name="cx-code",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="loop",
                name=LOOP_NAME,
                config={
                    "max": 3,
                    "until": "review.pass",
                    "commit_each_iteration": True,
                    "steps": [{"_cx_code_dispatch": {}}, {"_cx_code_review": {}}],
                },
            )
        ],
    )
    run = _start(pipeline, temp_git_repo, [Review("CONCERNS"), Review("PASS")], runs_dir)

    result = await _execute(run)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[-1].loop_commits is None
    assert len(_subjects(temp_git_repo)) == 3  # init and one commit per round
