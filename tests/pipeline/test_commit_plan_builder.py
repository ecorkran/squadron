"""Tests for build_commit_plan: candidate paths, staging, verdicts and messages (slice 196 D1, D2)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.commit_plan import (
    CommitSubject,
    CommitTarget,
    build_commit_plan,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from tests.conftest import run_test_git

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
TASKS_FILE = "project-documents/user/tasks/105-tasks.batch-foo.md"
PLAN_FILE = "project-documents/user/architecture/100-slices.plan-name.md"
ARCH_FILE = "project-documents/user/architecture/100-arch.plan-name.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.batch-foo.md"
TASKS_REVIEW = "project-documents/user/reviews/105-review.tasks.batch-foo.md"
CODE_REVIEW = "project-documents/user/reviews/105-review.code.batch-foo.md"
ARCH_REVIEW = "project-documents/user/reviews/100-review.arch.plan-name.md"


def _write(repo: Path, relative: str, text: str = "content\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _review(verdict: str) -> str:
    return f"---\ndocType: review\nverdict: {verdict}\n---\n\nbody\n"


def _cf() -> MagicMock:
    """A cf client shaped like the real one: the slice plan arrives as a bare stem."""
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=DESIGN_FILE, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.batch-foo.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file=ARCH_FILE,
        slice_plan="100-slices.plan-name",
        phase="Phase 4",
        slice=str(SLICE),
        name="squadron",
    )
    return client


def _target(
    subject: CommitSubject,
    *,
    template: str | None = None,
    round: int = 0,
    slice_index: int | None = SLICE,
    plan: str | None = None,
) -> CommitTarget:
    return CommitTarget(subject, slice_index, plan, template, round)


@pytest.fixture
def repo(temp_git_repo: Path) -> Path:
    """A repo where the planning files already exist and are committed."""
    _write(temp_git_repo, PLAN_FILE, "plan\n")
    _write(temp_git_repo, "DEVLOG.md", "devlog\n")
    _write(temp_git_repo, ARCH_FILE, "arch\n")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "planning files")
    return temp_git_repo


def _plan(repo: Path, target: CommitTarget):  # type: ignore[no-untyped-def]
    return build_commit_plan(target, repo, _cf())


# ---------------------------------------------------------------------------
# DESIGN
# ---------------------------------------------------------------------------


def test_design_stages_artifact_review_plan_and_devlog_only(repo: Path) -> None:
    _write(repo, DESIGN_FILE)
    _write(repo, DESIGN_REVIEW, _review("CONCERNS"))
    _write(repo, PLAN_FILE, "plan edited\n")
    _write(repo, "DEVLOG.md", "devlog edited\n")
    _write(repo, "stray.txt")

    plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))

    assert set(plan.paths) == {DESIGN_FILE, DESIGN_REVIEW, PLAN_FILE, "DEVLOG.md"}
    assert plan.left_out == ("stray.txt",)
    assert plan.stage_all is False
    assert plan.message == "docs: add slice 105 design (review: CONCERNS)"


def test_design_revision_round_reads_modified_status(repo: Path) -> None:
    _write(repo, DESIGN_FILE, "v1\n")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "design v1")
    _write(repo, DESIGN_FILE, "v2\n")
    _write(repo, DESIGN_REVIEW, _review("PASS"))

    plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice", round=2))

    assert plan.message == "docs: revise slice 105 design, round 2 (review: PASS)"


def test_review_only_round_zero_and_round_n(repo: Path) -> None:
    _write(repo, DESIGN_REVIEW, _review("CONCERNS"))

    round_zero = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))
    round_two = _plan(repo, _target(CommitSubject.DESIGN, template="slice", round=2))

    assert round_zero.message == "review: add slice 105 design review (CONCERNS)"
    assert round_two.message == "review: re-review slice 105 design, round 2 (CONCERNS)"


def test_nothing_dirty_means_no_paths(repo: Path) -> None:
    plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))
    assert plan.paths == ()
    assert plan.left_out == ()


def test_only_unrelated_files_dirty_means_no_paths_and_all_left_out(repo: Path) -> None:
    _write(repo, "stray.txt")
    _write(repo, "src/other.py")

    plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))

    assert plan.paths == ()
    assert plan.left_out == ("src/other.py", "stray.txt")


def test_untracked_file_inside_an_untracked_directory_is_found(repo: Path) -> None:
    """``-uall``: the artifact is not hidden behind its untracked parent directory."""
    _write(repo, DESIGN_FILE)

    plan = _plan(repo, _target(CommitSubject.DESIGN))

    assert plan.paths == (DESIGN_FILE,)


# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------


def test_tasks_candidates_and_message(repo: Path) -> None:
    _write(repo, TASKS_FILE)
    _write(repo, TASKS_REVIEW, _review("PASS"))
    _write(repo, DESIGN_FILE)  # a design edit is not a tasks candidate

    plan = _plan(repo, _target(CommitSubject.TASKS, template="tasks"))

    assert set(plan.paths) == {TASKS_FILE, TASKS_REVIEW}
    assert plan.left_out == (DESIGN_FILE,)
    assert plan.message == "docs: add slice 105 tasks (review: PASS)"


# ---------------------------------------------------------------------------
# ARCHITECTURE
# ---------------------------------------------------------------------------


def test_architecture_is_initiative_scoped(repo: Path) -> None:
    _write(repo, ARCH_FILE, "arch edited\n")
    _write(repo, ARCH_REVIEW, _review("PASS"))

    plan = _plan(
        repo,
        _target(CommitSubject.ARCHITECTURE, template="arch", slice_index=None, plan="100"),
    )

    assert set(plan.paths) == {ARCH_FILE, ARCH_REVIEW}
    assert plan.message == "docs: revise initiative 100 architecture (review: PASS)"


# ---------------------------------------------------------------------------
# DEVLOG
# ---------------------------------------------------------------------------


def test_devlog_stages_only_the_devlog(repo: Path) -> None:
    _write(repo, "DEVLOG.md", "devlog edited\n")
    _write(repo, DESIGN_FILE)

    plan = _plan(repo, _target(CommitSubject.DEVLOG))

    assert plan.paths == ("DEVLOG.md",)
    assert plan.left_out == (DESIGN_FILE,)
    assert plan.message == "docs: add DEVLOG entry for slice 105"


def test_devlog_without_a_slice(repo: Path) -> None:
    _write(repo, "DEVLOG.md", "devlog edited\n")

    plan = _plan(repo, _target(CommitSubject.DEVLOG, slice_index=None))

    assert plan.message == "docs: add DEVLOG entry"


# ---------------------------------------------------------------------------
# CODE
# ---------------------------------------------------------------------------


def test_code_stages_everything_dirty(repo: Path) -> None:
    _write(repo, "src/feature.py")
    _write(repo, "tests/test_feature.py")
    _write(repo, CODE_REVIEW, _review("PASS"))

    plan = _plan(repo, _target(CommitSubject.CODE, template="code"))

    assert plan.stage_all is True
    assert set(plan.paths) == {"src/feature.py", "tests/test_feature.py", CODE_REVIEW}
    assert plan.left_out == ()
    assert plan.message == "feat: implement slice 105 (review: PASS)"


def test_code_without_a_review_omits_the_clause(repo: Path) -> None:
    _write(repo, "src/feature.py")

    plan = _plan(repo, _target(CommitSubject.CODE, template="code"))

    assert plan.message == "feat: implement slice 105"


# ---------------------------------------------------------------------------
# Verdict is read from disk
# ---------------------------------------------------------------------------


def test_verdict_is_read_from_the_review_file_each_time(repo: Path) -> None:
    _write(repo, DESIGN_REVIEW, _review("CONCERNS"))
    first = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))
    _write(repo, DESIGN_REVIEW, _review("FAIL"))
    second = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))

    assert first.message.endswith("(CONCERNS)")
    assert second.message.endswith("(FAIL)")


def test_unreadable_verdict_omits_the_clause_and_warns(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(repo, DESIGN_FILE)
    _write(repo, DESIGN_REVIEW, "no frontmatter here\n")

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.commit_plan"):
        plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))

    assert plan.message == "docs: add slice 105 design"
    assert any("no readable verdict" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_slice_subject_without_a_slice_index_raises(repo: Path) -> None:
    with pytest.raises(ValueError, match="needs a slice index"):
        _plan(repo, _target(CommitSubject.DESIGN, slice_index=None))


def test_not_a_git_repository_raises(tmp_path: Path) -> None:
    with pytest.raises(GitEnvironmentError):
        build_commit_plan(_target(CommitSubject.DEVLOG), tmp_path, _cf())


def test_only_supporting_files_changed(repo: Path) -> None:
    """The slice plan or DEVLOG changed but neither the artifact nor a review did."""
    _write(repo, PLAN_FILE, "plan edited\n")

    plan = _plan(repo, _target(CommitSubject.DESIGN, template="slice"))

    assert plan.paths == (PLAN_FILE,)
    assert plan.message == "docs: update slice 105 design files"
