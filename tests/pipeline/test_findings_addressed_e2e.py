"""End-to-end coverage for the findings-addressed loop (slice 305 Part G).

Runs the target loop shape over a real git repository with a stubbed judge
transport, so the deterministic screens read genuine diffs and the per-round
commits are real. Only the model calls are faked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import squadron.pipeline.steps.gate  # noqa: F401 — register the gate step type
import squadron.pipeline.steps.loop  # noqa: F401 — register the loop step type
from squadron.pipeline.actions.checkpoint import CheckpointAction
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.gate import GateAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps import register_step_type
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict

_JUDGE_TRANSPORT = "squadron.review.addressed.judge.run_review_with_profile"
_TARGET_FILE = "src/x.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository with one commit — HEAD is the 'prior round'."""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    target = tmp_path / _TARGET_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("round 0\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def _mock_step_type(action_pairs: list[tuple[str, dict[str, object]]]) -> MagicMock:
    step_type = MagicMock()
    step_type.expand.return_value = action_pairs
    return step_type


def _finding(severity: Severity = Severity.CONCERN) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,
        title="a recurring problem",
        description="",
        category="correctness",
        location=f"{_TARGET_FILE}:12",
    )


def _review(verdict: str, findings: list[ReviewFinding]) -> ActionResult:
    """Build the review ActionResult the way ReviewAction does.

    Findings go through ``ReviewResult.structured_findings`` rather than being
    written as literal dicts: that property assigns the ``F00n`` ids and
    lowercases severity, and it is the only shape production ever hands the
    gate. A hand-built dict would pass tests that the real pipeline fails.
    """
    result = ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=findings,
        template_name="review",
        input_files={},
        raw_output="",
    )
    return ActionResult(
        success=True,
        action_type="review",
        outputs={},
        verdict=verdict,
        findings=[sf.__dict__ for sf in result.structured_findings],
    )


def _judge_output(text: str) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.UNKNOWN,
        findings=[],
        template_name="judge.findings-addressed",
        input_files={},
        raw_output=text,
    )


def _pipeline(*, checkpoint: str | None, suffix: str) -> PipelineDefinition:
    """The example pipeline's loop shape, with mock producer/assessor steps."""
    gate_config: dict[str, object] = {
        "name": "settled",
        "review_from": "fresh-review",
        "policy": "findings-addressed",
    }
    if checkpoint is not None:
        gate_config["checkpoint"] = checkpoint

    return PipelineDefinition(
        name="findings-addressed-e2e",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="loop",
                name="fix-loop",
                config={
                    "max": 3,
                    "until": "review.pass",
                    "commit_each_iteration": True,
                    "steps": [
                        {f"_fa_dispatch_{suffix}": {"name": "revise"}},
                        {f"_fa_review_{suffix}": {"name": "fresh-review"}},
                        {"gate": gate_config},
                    ],
                },
            )
        ],
    )


async def _run(
    repo: Path,
    *,
    dispatch: Any,
    reviews: list[ActionResult],
    checkpoint: str | None,
    suffix: str,
) -> Any:
    register_step_type(f"_fa_dispatch_{suffix}", _mock_step_type([("dispatch", {})]))
    register_step_type(f"_fa_review_{suffix}", _mock_step_type([("review", {})]))

    review_action = MagicMock()
    review_action.execute = AsyncMock(side_effect=reviews)

    return await execute_pipeline(
        _pipeline(checkpoint=checkpoint, suffix=suffix),
        {"slice": 305},
        resolver=MagicMock(**{"resolve.return_value": ("claude-sonnet-5", "sdk")}),
        cf_client=MagicMock(),
        cwd=str(repo),
        _action_registry={
            "dispatch": dispatch,
            "review": review_action,
            "gate": GateAction(),
            "commit": CommitAction(),
            "checkpoint": CheckpointAction(),
        },
    )


def _writing_dispatch(repo: Path) -> MagicMock:
    """A dispatch that actually changes the tree, one line per round."""
    rounds = iter(range(1, 10))

    async def _write(_context: ActionContext) -> ActionResult:
        target = repo / _TARGET_FILE
        target.write_text(f"round {next(rounds)}\n")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    action = MagicMock()
    action.execute = AsyncMock(side_effect=_write)
    return action


@pytest.mark.asyncio
async def test_three_rounds_screen0_then_fail_then_pass(repo: Path) -> None:
    """Round 1 annotates no-prior-round; round 2's recurring finding fails the
    gate and the loop continues; round 3's judged-addressed finding passes and
    the loop exits."""
    gate_metadata: list[dict[str, object]] = []

    transport = AsyncMock(return_value=_judge_output("F001: addressed"))
    reviews = [
        _review("FAIL", [_finding()]),
        _review("CONCERNS", [_finding()]),
        _review("PASS", []),
    ]

    with patch(_JUDGE_TRANSPORT, transport):
        result = await _run(
            repo,
            dispatch=_writing_dispatch(repo),
            reviews=reviews,
            checkpoint=None,
            suffix="happy",
        )

    assert result.status == ExecutionStatus.COMPLETED
    step_result = result.step_results[0]
    assert step_result.iteration == 3

    for action_result in step_result.action_results:
        if action_result.action_type == "gate":
            gate_metadata.append(action_result.metadata)

    # Only the final round's action_results survive on the StepResult, so the
    # per-round record is read from the evidence artifacts instead.
    reviews_dir = repo / "project-documents/user/reviews"
    written = sorted(path.name for path in reviews_dir.glob("305-gate.*"))
    assert written == [
        "305-gate.findings-addressed.settled-r1.md",
        "305-gate.findings-addressed.settled-r2.md",
        "305-gate.findings-addressed.settled-r3.md",
    ]

    round_1 = (reviews_dir / written[0]).read_text()
    assert "noPriorRound: true" in round_1
    assert "decidingScreen: no_prior_round" in round_1
    assert "addressedVerdict: PASS" in round_1
    assert "verdict: FAIL" in round_1  # reduced with the fresh review's FAIL

    round_2 = (reviews_dir / written[1]).read_text()
    assert "decidingScreen: null" in round_2
    assert "status: unaddressed" in round_2
    assert "screen: exact_match" in round_2
    assert "addressedVerdict: FAIL" in round_2

    round_3 = (reviews_dir / written[2]).read_text()
    assert "status: addressed" in round_3
    assert "screen: judge" in round_3
    assert "addressedVerdict: PASS" in round_3
    assert "verdict: PASS" in round_3

    # Screens are free: only round 3 had residue to judge.
    assert transport.await_count == 1
    assert gate_metadata[-1]["revision_number"] == 3
    assert gate_metadata[-1]["prior_round_sha"] is not None


@pytest.mark.asyncio
async def test_judge_failure_fails_closed_and_the_checkpoint_pauses(repo: Path) -> None:
    """Transport failure → addressed leg UNKNOWN → gate UNKNOWN → on-concerns
    checkpoint fires. It pauses the run: per issue #48 a checkpoint inside a
    loop body marks the loop complete, so the assertion is the pause, not a
    resumed loop."""
    transport = AsyncMock(side_effect=RuntimeError("provider exploded"))
    reviews = [
        _review("CONCERNS", [_finding()]),
        _review("PASS", []),
    ]

    with patch(_JUDGE_TRANSPORT, transport):
        result = await _run(
            repo,
            dispatch=_writing_dispatch(repo),
            reviews=reviews,
            # on-fail, not on-concerns: an on-concerns checkpoint would fire on
            # round 1's CONCERNS verdict and pause before the judge is ever
            # consulted. UNKNOWN fires both triggers, which is the point here.
            checkpoint="on-fail",
            suffix="failclosed",
        )

    assert result.status == ExecutionStatus.PAUSED
    step_result = result.step_results[0]
    assert step_result.iteration == 2

    gate_results = [r for r in step_result.action_results if r.action_type == "gate"]
    assert gate_results[-1].verdict == Verdict.UNKNOWN
    assert gate_results[-1].metadata["addressed_verdict"] == Verdict.UNKNOWN

    evidence = (
        repo / "project-documents/user/reviews/305-gate.findings-addressed.settled-r2.md"
    ).read_text()
    assert "addressedVerdict: UNKNOWN" in evidence


@pytest.mark.asyncio
async def test_byte_identical_round_fails_without_consulting_the_judge(repo: Path) -> None:
    """A round that changes nothing cannot have addressed anything — and pays
    no tokens to discover that."""
    transport = AsyncMock(side_effect=AssertionError("judge must not be consulted"))

    async def _noop(_context: ActionContext) -> ActionResult:
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch = MagicMock()
    dispatch.execute = AsyncMock(side_effect=_noop)

    reviews = [
        _review("CONCERNS", [_finding()]),
        _review("CONCERNS", []),
        _review("CONCERNS", []),
    ]

    with patch(_JUDGE_TRANSPORT, transport):
        result = await _run(
            repo,
            dispatch=dispatch,
            reviews=reviews,
            checkpoint=None,
            suffix="identical",
        )

    assert result.status == ExecutionStatus.FAILED  # exhausted without review.pass
    transport.assert_not_awaited()

    evidence = (
        repo / "project-documents/user/reviews/305-gate.findings-addressed.settled-r2.md"
    ).read_text()
    assert "decidingScreen: byte_identical" in evidence
    assert "addressedVerdict: FAIL" in evidence
