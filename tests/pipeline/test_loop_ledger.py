"""The loop commit ledger and its persistence (slice 202)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.loop_ledger import LoopCommitLedger, open_ledger, record_round_commit
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager, StepState
from tests.conftest import run_test_git

BASE_SHA = "a" * 40
COMMIT_SHAS = ["b" * 40, "c" * 40]


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
    ledger = LoopCommitLedger(base_sha=BASE_SHA, commits=COMMIT_SHAS)

    manager.record_step_completed(run_id, _paused_loop(ledger))
    persisted = manager.load(run_id).completed_steps[0]

    assert persisted.loop_commits == ledger


def test_unprovable_flag_round_trips(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})
    ledger = LoopCommitLedger(base_sha=BASE_SHA, commits=[], unprovable=True)

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


def _commit_file(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n")
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _phase_commit(sha: str, *, subject: str = "design", slice_index: int = SLICE) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="commit",
        outputs={"committed": True, "sha": sha, "commit_subject": subject, "slice": slice_index},
    )


def test_matching_phase_commit_at_head_joins_the_ledger(temp_git_repo: Path) -> None:
    parent = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()
    head = _commit_file(temp_git_repo, "design.md")
    prior = {"design:commit:0": _phase_commit(head)}

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=parent, commits=[head])


def test_phase_commit_for_a_different_document_is_left_out_with_a_warning(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    head = _commit_file(temp_git_repo, "tasks.md")
    prior = {"tasks:commit:0": _phase_commit(head, subject="tasks")}

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head)
    assert sum("different document" in r.message for r in caplog.records) == 1


def test_phase_commit_for_a_different_slice_is_left_out(temp_git_repo: Path) -> None:
    head = _commit_file(temp_git_repo, "design.md")
    prior = {"design:commit:0": _phase_commit(head, slice_index=SLICE + 1)}

    ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head)


def test_phase_commit_not_at_head_is_left_out(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    phase_sha = _commit_file(temp_git_repo, "design.md")
    operator_sha = _commit_file(temp_git_repo, "operator.md")
    prior = {"design:commit:0": _phase_commit(phase_sha)}

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), prior, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=operator_sha)
    assert sum("is not HEAD" in r.message for r in caplog.records) == 1


def test_no_prior_commit_result_gives_an_empty_ledger_without_a_warning(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    head = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()
    skipped = ActionResult(success=True, action_type="commit", outputs={"committed": False})

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), {"design:commit:0": skipped}, str(temp_git_repo))

    assert ledger == LoopCommitLedger(base_sha=head)
    assert caplog.records == []


def test_code_loop_gets_no_ledger(temp_git_repo: Path) -> None:
    params = {**_loop_params(CommitSubject.CODE), "review_template": "code"}

    assert open_ledger(params, {}, str(temp_git_repo)) is None


def test_phase_commit_that_is_the_root_commit_is_unprovable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo = tmp_path / "root-repo"
    repo.mkdir()
    run_test_git(repo, "init", "-q", "-b", "main")
    head = _commit_file(repo, "design.md")
    prior = {"design:commit:0": _phase_commit(head)}

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), prior, str(repo))

    assert ledger is not None
    assert ledger.unprovable is True
    assert sum("has no parent" in r.message for r in caplog.records) == 1


def test_unreadable_head_is_unprovable(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        ledger = open_ledger(_loop_params(), {}, str(not_a_repo))

    assert ledger == LoopCommitLedger(base_sha="", unprovable=True)
    assert sum("cannot read HEAD" in r.message for r in caplog.records) == 1


# ---------------------------------------------------------------------------
# record_round_commit
# ---------------------------------------------------------------------------


def _round_commit(sha: str) -> ActionResult:
    return ActionResult(success=True, action_type="commit", outputs={"committed": True, "sha": sha})


def test_round_commits_are_appended_in_order() -> None:
    ledger = LoopCommitLedger(base_sha=BASE_SHA)

    for sha in COMMIT_SHAS:
        record_round_commit(ledger, _round_commit(sha))

    assert ledger.commits == COMMIT_SHAS
    assert ledger.unprovable is False


def test_a_round_that_committed_nothing_adds_nothing() -> None:
    ledger = LoopCommitLedger(base_sha=BASE_SHA)
    nothing = ActionResult(success=True, action_type="commit", outputs={"committed": False})

    record_round_commit(ledger, nothing)

    assert ledger == LoopCommitLedger(base_sha=BASE_SHA)


def test_a_failed_round_commit_adds_nothing() -> None:
    ledger = LoopCommitLedger(base_sha=BASE_SHA)
    failed = ActionResult(success=False, action_type="commit", outputs={}, error="hook rejected")

    record_round_commit(ledger, failed)

    assert ledger == LoopCommitLedger(base_sha=BASE_SHA)


def test_an_unknown_sha_makes_the_ledger_unprovable(caplog: pytest.LogCaptureFixture) -> None:
    ledger = LoopCommitLedger(base_sha=BASE_SHA, commits=[COMMIT_SHAS[0]])

    with caplog.at_level(logging.WARNING, logger=LEDGER_LOGGER):
        record_round_commit(ledger, _round_commit("unknown"))

    assert ledger.unprovable is True
    assert ledger.commits == [COMMIT_SHAS[0]]
    assert sum("sha is unknown" in r.message for r in caplog.records) == 1
