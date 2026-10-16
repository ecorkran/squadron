"""The git history log pass against a real temporary repo (slice 176 D6, D9)."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from squadron.review.git_utils import run_git
from squadron.stats.git_history import GitHistory, GitHistoryError
from tests.stats.repo_support import StatsRepo

_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_T3 = "2026-10-03T10:00:00+00:00"
_T4 = "2026-10-04T10:00:00+00:00"
_TASKS = "project-documents/user/tasks/176-tasks.x.md"
_REVIEW = "project-documents/user/reviews/176-review.code.x.md"


class CountingRunner:
    """The real ``run_git`` with a call log, so a test can assert the call count."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        self.calls.append(args)
        return run_git(args, cwd=cwd)


@pytest.fixture
def slice_repo(stats_repo: StatsRepo) -> StatsRepo:
    """main (init), then a ``176-slice.x`` branch: task file, code, doc edit, merge back."""
    stats_repo.commit("init", {"README.md": "init\n"}, _T1)
    stats_repo.branch("176-slice.x")
    stats_repo.commit("docs: add tasks", {_TASKS: "# tasks\n"}, _T2)
    stats_repo.commit("feat: code", {"src/a.py": "a = 1\n"}, _T3)
    stats_repo.commit("docs: edit tasks", {_TASKS: "# tasks v2\n"}, _T4)
    return stats_repo


def _loaded(repo: StatsRepo, runner: CountingRunner | None = None) -> GitHistory:
    history = GitHistory(repo.root, run=runner or run_git)
    history.load()
    return history


def test_graph_holds_parents_dates_subjects_and_changes_with_blob_ids(
    slice_repo: StatsRepo,
) -> None:
    history = _loaded(slice_repo)
    tip = history.branch_tip(176)
    assert tip is not None

    chain = history.first_parent_chain(tip)

    assert [c.subject for c in chain] == ["docs: edit tasks", "feat: code", "docs: add tasks", "init"]
    assert chain[0].parents == (chain[1].sha,)
    assert chain[-1].parents == ()
    assert chain[1].authored_at == datetime.fromisoformat(_T3)
    code = chain[1].changes
    assert [(c.status, c.path) for c in code] == [("A", "src/a.py")]
    assert code[0].blob_id == slice_repo.blob(chain[1].sha, "src/a.py")
    modified = chain[0].changes
    assert [(c.status, c.path) for c in modified] == [("M", _TASKS)]
    assert modified[0].blob_id == slice_repo.blob(chain[0].sha, _TASKS)


def test_a_merge_commit_has_two_parents(slice_repo: StatsRepo) -> None:
    slice_repo.checkout("main")
    merge_sha = slice_repo.merge("176-slice.x", "merge slice", "2026-10-05T10:00:00+00:00")

    merge = _loaded(slice_repo).commit(merge_sha)

    assert len(merge.parents) == 2


def test_a_move_into_archive_is_a_delete_plus_an_add_never_a_rename(
    slice_repo: StatsRepo,
) -> None:
    archived = "project-documents/user/tasks/archive/176-tasks.x.md"
    sha = slice_repo.move("docs: archive tasks", _TASKS, archived, "2026-10-06T10:00:00+00:00")

    changes = _loaded(slice_repo).commit(sha).changes

    assert sorted((c.status, c.path) for c in changes) == [("A", archived), ("D", _TASKS)]
    added = next(c for c in changes if c.status == "A")
    assert added.blob_id == slice_repo.blob(sha, archived)


def test_load_makes_exactly_two_git_calls(slice_repo: StatsRepo) -> None:
    runner = CountingRunner()

    _loaded(slice_repo, runner)

    assert len(runner.calls) == 2
    assert runner.calls[0][0] == "for-each-ref"
    assert "log" in runner.calls[1]


def test_queries_find_the_branch_tip_and_the_commit_that_added_a_path(
    slice_repo: StatsRepo,
) -> None:
    history = _loaded(slice_repo)

    added = history.first_added("project-documents/user/tasks/176-tasks.*.md")
    touching = history.commits_touching("project-documents/user/tasks/176-tasks.*.md")

    assert added is not None and added.subject == "docs: add tasks"
    assert [c.subject for c in touching] == ["docs: edit tasks", "docs: add tasks"]
    assert history.branch_tip(999) is None


def test_a_directory_that_is_not_a_repo_names_the_cwd(tmp_path: Path) -> None:
    history = GitHistory(tmp_path / "nowhere-a-repo")
    (tmp_path / "nowhere-a-repo").mkdir()

    with pytest.raises(GitHistoryError) as raised:
        history.load()

    assert str(tmp_path / "nowhere-a-repo") in str(raised.value)
    assert raised.value.command.startswith("git for-each-ref")


def test_a_runner_that_cannot_answer_names_the_command_and_leaves_no_graph(
    slice_repo: StatsRepo,
) -> None:
    def runner(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        return None if "log" in args else run_git(args, cwd=cwd)

    history = GitHistory(slice_repo.root, run=runner)

    with pytest.raises(GitHistoryError) as raised:
        history.load()

    assert "git -c core.quotepath=off log" in raised.value.command
    with pytest.raises(RuntimeError, match=r"load\(\)"):
        history.first_added("*")


def test_show_returns_text_and_warns_when_git_cannot_produce_it(
    slice_repo: StatsRepo, caplog: pytest.LogCaptureFixture
) -> None:
    history = _loaded(slice_repo)
    tip = history.branch_tip(176)
    assert tip is not None

    assert history.show(tip.sha, _TASKS) == "# tasks v2\n"
    with caplog.at_level(logging.WARNING, logger="squadron.stats.git_history"):
        assert history.show(tip.sha, "no/such/file.md") is None
    assert any("no/such/file.md" in r.getMessage() for r in caplog.records)
