"""Proof checks and the composed message of a loop collapse (slice 202)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from squadron.integrations.context_forge import ProjectInfo, SliceEntry
from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.loop_collapse import (
    CollapseOutcome,
    CollapseResult,
    check_collapse,
    collapse_message,
)
from squadron.pipeline.loop_ledger import LoopCommitLedger
from tests.conftest import run_test_git

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.batch-foo.md"
TARGET = "main"


def _git(repo: Path, *args: str) -> str:
    return run_test_git(repo, *args).strip()


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _commit(repo: Path, files: dict[str, str], message: str = "loop commit") -> str:
    """Write ``files`` and commit them; returns the new sha."""
    for relative, text in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        _git(repo, "add", relative)
    _git(repo, "commit", "-q", "-m", message)
    return _head(repo)


def _loop_of(repo: Path, count: int) -> LoopCommitLedger:
    """``count`` loop-style commits on top of HEAD, and the ledger that proves them."""
    base = _head(repo)
    commits = [_commit(repo, {f"round{n}.md": f"round {n}\n"}) for n in range(1, count + 1)]
    return LoopCommitLedger(base_sha=base, commits=commits)


def _loop_params() -> dict[str, object]:
    return {
        "commit_subject": CommitSubject.DESIGN,
        "review_template": "slice",
        "slice": str(SLICE),
    }


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(
            index=SLICE,
            name="Batch Foo",
            design_file=DESIGN_FILE,
            status="in_progress",
            retroactive=False,
        )
    ]
    client.get_project.return_value = ProjectInfo(
        arch_file="project-documents/user/architecture/100-arch.plan-name.md",
        slice_plan="100-slices.plan-name",
        phase="Phase 4",
        slice=str(SLICE),
        name="squadron",
    )
    client.get_config.return_value = ""
    return client


# ---------------------------------------------------------------------------
# Proof checks (D3)
# ---------------------------------------------------------------------------


def test_a_proven_tail_is_collapsible(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 3)

    assert check_collapse(ledger, TARGET, str(temp_git_repo)) is None


def test_fewer_than_two_commits_is_nothing_to_collapse(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 1)

    result = check_collapse(ledger, TARGET, str(temp_git_repo))

    assert result == CollapseResult(CollapseOutcome.NOTHING_TO_COLLAPSE)


def _assert_refused(
    repo: Path, ledger: LoopCommitLedger, reason_contains: str, target: str = TARGET
) -> None:
    before = (_head(repo), _git(repo, "branch", "--show-current"))

    result = check_collapse(ledger, target, str(repo))

    assert result is not None
    assert result.outcome is CollapseOutcome.REFUSED
    assert reason_contains in result.reason
    assert (_head(repo), _git(repo, "branch", "--show-current")) == before


def test_an_unprovable_ledger_is_refused(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 2)
    ledger.unprovable = True

    _assert_refused(temp_git_repo, ledger, "cannot prove")


def test_an_unprovable_ledger_with_no_commits_is_still_refused(temp_git_repo: Path) -> None:
    ledger = LoopCommitLedger(base_sha="", unprovable=True)

    _assert_refused(temp_git_repo, ledger, "cannot prove")


def test_off_the_target_branch_is_refused(temp_git_repo: Path) -> None:
    _git(temp_git_repo, "checkout", "-q", "-b", "scratch")
    ledger = _loop_of(temp_git_repo, 2)

    _assert_refused(temp_git_repo, ledger, "on scratch, not the target main")


def test_a_detached_head_is_refused(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 2)
    _git(temp_git_repo, "checkout", "-q", "--detach")

    _assert_refused(temp_git_repo, ledger, "detached HEAD")


def test_head_past_the_last_loop_commit_is_refused(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 2)
    operator = _commit(temp_git_repo, {"operator.md": "mine\n"})

    _assert_refused(temp_git_repo, ledger, f"HEAD {operator} is not the loop's last commit")


def test_an_operator_commit_between_loop_commits_is_refused(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    first = _commit(temp_git_repo, {"round1.md": "1\n"})
    _commit(temp_git_repo, {"operator.md": "mine\n"})
    last = _commit(temp_git_repo, {"round2.md": "2\n"})
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    _assert_refused(temp_git_repo, ledger, "not the loop's")


def test_a_merge_commit_in_the_range_is_refused(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    first = _commit(temp_git_repo, {"round1.md": "1\n"})
    _git(temp_git_repo, "checkout", "-q", "-b", "side", base)
    _commit(temp_git_repo, {"side.md": "side\n"})
    _git(temp_git_repo, "checkout", "-q", TARGET)
    _git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    last = _commit(temp_git_repo, {"round2.md": "2\n"})
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    _assert_refused(temp_git_repo, ledger, "not the loop's")


def test_a_remote_ref_containing_the_first_commit_is_refused(temp_git_repo: Path) -> None:
    ledger = _loop_of(temp_git_repo, 2)
    _git(temp_git_repo, "update-ref", "refs/remotes/origin/x", ledger.commits[0])

    _assert_refused(
        temp_git_repo, ledger, f"commit {ledger.commits[0]} is already on refs/remotes/origin/x"
    )


def test_a_failing_git_command_is_git_failed_with_the_command_text(
    temp_git_repo: Path,
) -> None:
    ledger = _loop_of(temp_git_repo, 2)
    ledger.base_sha = "0" * 40  # not an object: rev-list refuses

    result = check_collapse(ledger, TARGET, str(temp_git_repo))

    assert result is not None
    assert result.outcome is CollapseOutcome.GIT_FAILED
    assert f"git rev-list --first-parent {'0' * 40}..HEAD" in result.reason


# ---------------------------------------------------------------------------
# The surviving message (D4)
# ---------------------------------------------------------------------------


def _round(repo: Path, design_text: str, verdict: str) -> str:
    return _commit(
        repo,
        {DESIGN_FILE: design_text, DESIGN_REVIEW: f"---\nverdict: {verdict}\n---\n"},
    )


def test_a_collapse_that_includes_the_phase_commit_reads_as_an_add(temp_git_repo: Path) -> None:
    base = _head(temp_git_repo)
    phase = _commit(temp_git_repo, {DESIGN_FILE: "v1\n"})
    first = _round(temp_git_repo, "v2\n", "CONCERNS")
    last = _round(temp_git_repo, "v3\n", "PASS")
    ledger = LoopCommitLedger(base_sha=base, commits=[phase, first, last])

    message = collapse_message(ledger, _loop_params(), str(temp_git_repo), _cf())

    assert message == "docs: add slice 105 design (review: PASS)"


def test_a_collapse_of_rounds_over_an_existing_document_reads_as_a_revise(
    temp_git_repo: Path,
) -> None:
    _commit(temp_git_repo, {DESIGN_FILE: "v1\n"})
    base = _head(temp_git_repo)
    first = _round(temp_git_repo, "v2\n", "CONCERNS")
    last = _round(temp_git_repo, "v3\n", "PASS")
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    message = collapse_message(ledger, _loop_params(), str(temp_git_repo), _cf())

    assert message == "docs: revise slice 105 design (review: PASS)"


def test_the_verdict_is_the_final_reviews_not_the_first(temp_git_repo: Path) -> None:
    _commit(temp_git_repo, {DESIGN_FILE: "v1\n"})
    base = _head(temp_git_repo)
    first = _round(temp_git_repo, "v2\n", "PASS")
    last = _round(temp_git_repo, "v3\n", "CONCERNS")
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    message = collapse_message(ledger, _loop_params(), str(temp_git_repo), _cf())

    assert message.endswith("(review: CONCERNS)")


def test_files_outside_the_documents_scope_do_not_change_the_message(
    temp_git_repo: Path,
) -> None:
    _commit(temp_git_repo, {DESIGN_FILE: "v1\n"})
    base = _head(temp_git_repo)
    first = _commit(temp_git_repo, {DESIGN_FILE: "v2\n", "unrelated.txt": "x\n"})
    last = _round(temp_git_repo, "v3\n", "PASS")
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    message = collapse_message(ledger, _loop_params(), str(temp_git_repo), _cf())

    assert message == "docs: revise slice 105 design (review: PASS)"


def test_the_message_never_reads_the_replaced_commit_messages(temp_git_repo: Path) -> None:
    _commit(temp_git_repo, {DESIGN_FILE: "v1\n"})
    base = _head(temp_git_repo)
    first = _commit(temp_git_repo, {DESIGN_FILE: "v2\n"}, "docs: revise slice 999 tasks, round 7")
    last = _round(temp_git_repo, "v3\n", "PASS")
    ledger = LoopCommitLedger(base_sha=base, commits=[first, last])

    message = collapse_message(ledger, _loop_params(), str(temp_git_repo), _cf())

    assert "999" not in message
