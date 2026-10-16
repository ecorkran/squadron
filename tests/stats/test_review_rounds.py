"""Per-round review verdicts from committed versions (slice 176 D6, D9)."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime

import pytest

from squadron.review.git_utils import run_git
from squadron.stats import review_rounds as review_rounds_module
from squadron.stats.git_history import GitHistory
from squadron.stats.review_rounds import review_rounds, rounds_to_accept
from tests.stats.repo_support import CountingRunner, StatsRepo

_REVIEW = "project-documents/user/reviews/176-review.tasks.x.md"
_ARCHIVED = "project-documents/user/reviews/archive/176-review.tasks.x.20261001T120000.md"
_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_T3 = "2026-10-03T10:00:00+00:00"
_T4 = "2026-10-04T10:00:00+00:00"


def _artifact(verdict: str) -> str:
    front = f"docType: review\nverdict: {verdict}\naiModel: m-{verdict.lower()}\nrunId: run-1"
    return f"---\n{front}\n---\n\nBody {verdict}\n"


@pytest.fixture
def review_repo(stats_repo: StatsRepo) -> StatsRepo:
    """FAIL, then an archive copy of it, then CONCERNS, then PASS."""
    stats_repo.commit("init", {"README.md": "x\n"}, _T1)
    stats_repo.commit("review 1", {_REVIEW: _artifact("FAIL")}, _T1)
    stats_repo.commit("archive round 1", {_ARCHIVED: _artifact("FAIL")}, _T2)
    stats_repo.commit("review 2", {_REVIEW: _artifact("CONCERNS")}, _T3)
    stats_repo.commit("review 3", {_REVIEW: _artifact("PASS")}, _T4)
    return stats_repo


def _history(repo: StatsRepo, runner: CountingRunner | None = None) -> GitHistory:
    history = GitHistory(repo.root, run=runner or run_git)
    history.load()
    return history


def test_three_versions_plus_an_archive_copy_are_three_rounds(review_repo: StatsRepo) -> None:
    result = review_rounds(_history(review_repo), 176, "tasks")

    assert [r.verdict for r in result.rounds] == ["FAIL", "CONCERNS", "PASS"]
    assert [r.model for r in result.rounds] == ["m-fail", "m-concerns", "m-pass"]
    assert {r.run_id for r in result.rounds} == {"run-1"}
    assert result.skipped == 0
    assert rounds_to_accept(result.rounds) == 2


def test_the_kept_commit_of_a_duplicate_blob_is_the_earliest(review_repo: StatsRepo) -> None:
    result = review_rounds(_history(review_repo), 176, "tasks")

    assert result.rounds[0].authored_at == datetime.fromisoformat(_T1)  # not the archive copy's _T2


def test_other_review_types_are_not_mixed_in(review_repo: StatsRepo) -> None:
    assert review_rounds(_history(review_repo), 176, "slice").rounds == ()
    assert review_rounds(_history(review_repo), 17, "tasks").rounds == ()


def test_no_round_is_accepted_when_none_passes(review_repo: StatsRepo) -> None:
    result = review_rounds(_history(review_repo), 176, "tasks")

    assert rounds_to_accept(result.rounds[:1]) is None
    assert rounds_to_accept(()) is None


@pytest.mark.parametrize(("cutoff", "expected"), [("2026-09-01", False), ("2026-11-01", True)])
def test_lower_bound_is_set_only_when_the_earliest_round_predates_the_cutoff(
    review_repo: StatsRepo, monkeypatch: pytest.MonkeyPatch, cutoff: str, expected: bool
) -> None:
    monkeypatch.setattr(
        review_rounds_module,
        "COMMIT_EACH_ITERATION_SINCE",
        datetime.fromisoformat(f"{cutoff}T00:00:00+00:00"),
    )

    assert review_rounds(_history(review_repo), 176, "tasks").lower_bound is expected


def test_broken_frontmatter_and_a_failing_git_show_are_each_skipped_with_a_warning(
    stats_repo: StatsRepo, caplog: pytest.LogCaptureFixture
) -> None:
    stats_repo.commit("init", {"README.md": "x\n"}, _T1)
    stats_repo.commit("good", {_REVIEW: _artifact("CONCERNS")}, _T2)
    broken = stats_repo.commit("broken", {_REVIEW: "no frontmatter at all\n"}, _T3)
    unshowable = stats_repo.commit("unshowable", {_REVIEW: _artifact("PASS")}, _T4)

    def runner(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[0] == "show" and args[1].startswith(unshowable):
            return None
        return run_git(args, cwd=cwd)

    history = GitHistory(stats_repo.root, run=runner)
    history.load()
    with caplog.at_level(logging.WARNING):
        result = review_rounds(history, 176, "tasks")

    assert [r.verdict for r in result.rounds] == ["CONCERNS"]
    assert result.skipped == 2
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(broken in m and _REVIEW in m for m in messages)
    assert any(unshowable in m and _REVIEW in m for m in messages)


def test_git_call_count_is_two_plus_the_versions_read(review_repo: StatsRepo) -> None:
    runner = CountingRunner()
    history = _history(review_repo, runner)

    review_rounds(history, 176, "tasks")

    assert len(runner.calls) == 2 + 3
    assert [call[0] for call in runner.calls].count("show") == 3
