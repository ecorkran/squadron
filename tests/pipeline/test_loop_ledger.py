"""The loop commit ledger and its persistence (slice 202)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.head_stamp import HEAD_AFTER_KEY, HEAD_BEFORE_KEY
from squadron.pipeline.loop_ledger import LoopCommitLedger, claim_actions, open_ledger
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager, StepState
from tests.conftest import run_test_git

BASE_SHA = "a" * 40
TIP_SHA = "b" * 40


def _paused_loop(ledger: LoopCommitLedger | None) -> StepResult:
    return StepResult(
        step_name="rounds",
        step_type="loop",
        status=ExecutionStatus.PAUSED,
        action_results=[],
        iteration=2,
        loop_commits=ledger,
    )


def test_ledger_round_trips_through_the_state_file(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})
    ledger = LoopCommitLedger(base_sha=BASE_SHA, tip_sha=TIP_SHA, commit_count=2)

    manager.record_step_completed(run_id, _paused_loop(ledger))
    persisted = manager.load(run_id).completed_steps[0]

    assert persisted.loop_commits == ledger


def test_unprovable_flag_round_trips(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})
    ledger = LoopCommitLedger(base_sha=BASE_SHA, tip_sha=BASE_SHA, unprovable=True)

    manager.record_step_completed(run_id, _paused_loop(ledger))

    assert manager.load(run_id).completed_steps[0].loop_commits == ledger


def test_step_without_a_ledger_persists_none(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})

    manager.record_step_completed(run_id, _paused_loop(None))

    assert manager.load(run_id).completed_steps[0].loop_commits is None


def test_state_file_written_without_loop_commits_still_loads() -> None:
    older = {
        "step_name": "rounds",
        "step_type": "loop",
        "status": "paused",
        "action_results": [],
        "iteration": 2,
        "completed_at": datetime.now(UTC).isoformat(),
    }

    assert StepState.model_validate(older).loop_commits is None


# ---------------------------------------------------------------------------
# open_ledger (D1, D7)
# ---------------------------------------------------------------------------

LEDGER_LOGGER = "squadron.pipeline.loop_ledger"
SLICE = 202


def _loop_params(subject: CommitSubject = CommitSubject.DESIGN) -> dict[str, object]:
    return {"commit_subject": subject, "review_template": "slice", "slice": str(SLICE)}


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _commit_file(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n")
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")
    return _head(repo)


def _stamped(action_type: str, before: str, after: str, **outputs: object) -> ActionResult:
    return ActionResult(
        success=True,
        action_type=action_type,
        outputs=dict(outputs),
        metadata={HEAD_BEFORE_KEY: before, HEAD_AFTER_KEY: after},
    )


def _phase_commit(
    before: str, after: str, *, subject: str = "design", slice_index: int = SLICE
) -> ActionResult:
    return _stamped(
        "commit",
        before,
        after,
        committed=True,
        sha=after,
        commit_subject=subject,
        slice=slice_index,
    )


def test_phase_commit_and_the_agent_commit_before_it_join_the_ledger(
    temp_git_repo: Path,
) -> None:
    base = _head(temp_git_repo)
    agent = _commit_file(temp_git_repo, "agent.md")
    phase = _commit_file(temp_git_repo, "design.md")
    prior = {
        "design:dispatch:0": _stamped("dispatch", base, agent),
        "design:commit:1": _phase_commit(agent, phase),
    }

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=base, tip_sha=phase, commit_count=2)


def test_a_phase_commit_with_no_agent_commit_before_it_starts_at_its_parent(
    temp_git_repo: Path,
) -> None:
    base = _head(temp_git_repo)
    phase = _commit_file(temp_git_repo, "design.md")
    prior = {"design:commit:0": _phase_commit(base, phase)}

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=base, tip_sha=phase, commit_count=1)


def test_an_earlier_documents_dispatch_is_not_pulled_in(temp_git_repo: Path) -> None:
    root = _head(temp_git_repo)
    earlier_agent = _commit_file(temp_git_repo, "earlier.md")
    base = _commit_file(temp_git_repo, "operator.md")  # a commit no action of this step made
    phase = _commit_file(temp_git_repo, "design.md")
    prior = {
        "earlier:dispatch:0": _stamped("dispatch", root, earlier_agent),
        "design:commit:0": _phase_commit(base, phase),
    }

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=base, tip_sha=phase, commit_count=1)


def test_phase_commit_for_a_different_document_is_left_out_with_a_warning(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    base = _head(temp_git_repo)
    head = _commit_file(temp_git_repo, "tasks.md")
    prior = {"tasks:commit:0": _phase_commit(base, head, subject="tasks")}

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head, tip_sha=head)
    assert sum("different document" in r.message for r in caplog.records) == 1


def test_phase_commit_for_a_different_slice_is_left_out(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    head = _commit_file(temp_git_repo, "design.md")
    prior = {"design:commit:0": _phase_commit(base, head, slice_index=SLICE + 1)}

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head, tip_sha=head)


def test_phase_commit_not_at_head_is_left_out(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    base = _head(temp_git_repo)
    phase = _commit_file(temp_git_repo, "design.md")
    operator = _commit_file(temp_git_repo, "operator.md")
    prior = {"design:commit:0": _phase_commit(base, phase)}

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=operator, tip_sha=operator)
    assert sum("is not HEAD" in r.message for r in caplog.records) == 1


def test_a_phase_commit_without_stamps_is_left_out(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    head = _commit_file(temp_git_repo, "design.md")
    unstamped = ActionResult(
        success=True,
        action_type="commit",
        outputs={"committed": True, "sha": head, "commit_subject": "design", "slice": SLICE},
    )

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), {"design:commit:0": unstamped}, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head, tip_sha=head)
    assert sum("no HEAD stamp" in r.message for r in caplog.records) == 1


def test_no_prior_commit_result_gives_an_empty_ledger_without_a_warning(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    head = _head(temp_git_repo)
    skipped = _stamped("commit", head, head, committed=False)

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), {"design:commit:0": skipped}, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head, tip_sha=head)
    assert caplog.records == []


def test_code_loop_gets_no_ledger(temp_git_repo: Path) -> None:
    params = {**_loop_params(CommitSubject.CODE), "review_template": "code"}

    assert open_ledger(params, {}, str(temp_git_repo)) is None


def test_unreadable_head_is_unprovable(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), {}, str(not_a_repo))

    assert ledger == LoopCommitLedger(base_sha="", tip_sha="", unprovable=True)
    assert sum("cannot read HEAD" in r.message for r in caplog.records) == 1


# ---------------------------------------------------------------------------
# claim_actions
# ---------------------------------------------------------------------------


def test_a_round_that_chains_from_the_tip_is_claimed(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    agent = _commit_file(temp_git_repo, "agent.md")
    round_commit = _commit_file(temp_git_repo, "round.md")
    ledger = LoopCommitLedger(base_sha=base, tip_sha=base)
    review = ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")

    claim_actions(
        ledger,
        [
            _stamped("dispatch", base, agent),
            review,
            _stamped("commit", agent, round_commit, committed=True, sha=round_commit),
        ],
        str(temp_git_repo),
    )

    assert ledger == LoopCommitLedger(base_sha=base, tip_sha=round_commit, commit_count=2)


def test_an_action_that_committed_nothing_claims_nothing(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    ledger = LoopCommitLedger(base_sha=base, tip_sha=base)

    claim_actions(ledger, [_stamped("dispatch", base, base)], str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=base, tip_sha=base)


def test_a_commit_between_actions_makes_the_ledger_unprovable(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    base = _head(temp_git_repo)
    operator = _commit_file(temp_git_repo, "operator.md")
    agent = _commit_file(temp_git_repo, "agent.md")
    ledger = LoopCommitLedger(base_sha=base, tip_sha=base)

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        claim_actions(ledger, [_stamped("dispatch", operator, agent)], str(temp_git_repo))

    assert ledger.unprovable is True
    assert ledger.tip_sha == base and ledger.commit_count == 0
    assert sum(f"not the loop's last commit {base}" in r.message for r in caplog.records) == 1


def test_a_dispatch_without_stamps_makes_the_ledger_unprovable(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    ledger = LoopCommitLedger(base_sha=base, tip_sha=base)
    unstamped = ActionResult(success=True, action_type="dispatch", outputs={})

    claim_actions(ledger, [unstamped], str(temp_git_repo))

    assert ledger.unprovable is True


def test_nothing_is_claimed_once_the_ledger_is_unprovable(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    agent = _commit_file(temp_git_repo, "agent.md")
    ledger = LoopCommitLedger(base_sha=base, tip_sha=base, unprovable=True)

    claim_actions(ledger, [_stamped("dispatch", base, agent)], str(temp_git_repo))

    assert ledger.tip_sha == base and ledger.commit_count == 0
