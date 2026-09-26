"""Tests for input gathering (D7): commits, slice artifacts, and the review scan."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ContextForgeNotAvailable, SliceEntry, TaskEntry
from squadron.pr.inputs import (
    EmptyCommitRangeError,
    find_latest_in_range_review,
    gather_commits_and_slice,
)
from squadron.review.git_utils import CommitRecord, GitRangeUnavailableError
from squadron.review.models import Verdict
from tests.pr.conftest import commit

SLICE_BRANCH = "385-slice.create-a-pr-with-a-good-message"
NON_SLICE_BRANCH = "scratch-branch"
HOST, OWNER, REPOSITORY = "github.com", "ecorkran", "squadron"


def _cf_client(*, slices: list[SliceEntry], tasks: list[TaskEntry]) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = slices
    client.list_tasks.return_value = tasks
    return client


def _fake_commits_in_range(base: str, head: str, *, cwd: str) -> list[CommitRecord]:
    return [CommitRecord(sha="abc123", subject="feat: do the thing")]


@pytest.fixture(autouse=True)
def _fake_commits(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setattr("squadron.pr.inputs.commits_in_range", _fake_commits_in_range)


def test_slice_branch_with_design_and_tasks(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "project-documents" / "user" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_file = tasks_dir / "385-tasks.create-a-pr-with-a-good-message.md"
    task_file.write_text("- [x] done\n- [ ] not done\n")
    slices_dir = tmp_path / "project-documents" / "user" / "slices"
    slices_dir.mkdir(parents=True)
    design_text = "# Slice Design: Create a PR with a Good Message\n\nWhy it exists.\n"
    (slices_dir / "385-slice.create-a-pr-with-a-good-message.md").write_text(design_text)

    cf_client = _cf_client(
        slices=[
            SliceEntry(
                index=385,
                name="Create a PR with a Good Message",
                design_file="project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md",
                status="not_started",
            )
        ],
        tasks=[TaskEntry(index=385, files=["385-tasks.create-a-pr-with-a-good-message.md"])],
    )

    result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is not None
    # Read relative to ``cwd``, not the process's own working directory.
    assert result.slice.design_text == design_text
    assert result.slice.task_items is not None
    assert result.slice.task_items.checked == ("done",)
    assert result.slice.task_items.unchecked == ("not done",)
    assert len(result.commits) == 1


def test_slice_branch_cf_does_not_know_degrades_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = _cf_client(slices=[], tasks=[])

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    assert any("385" in record.message for record in caplog.records)


def test_non_slice_branch_makes_no_cf_call(tmp_path: Path) -> None:
    cf_client = _cf_client(slices=[], tasks=[])

    result = gather_commits_and_slice(cf_client, base="main", head=NON_SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index is None
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    cf_client.list_slices.assert_not_called()


def test_task_file_absent_leaves_design_present_and_items_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = _cf_client(
        slices=[
            SliceEntry(
                index=385,
                name="Create a PR with a Good Message",
                design_file="project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md",
                status="not_started",
            )
        ],
        tasks=[TaskEntry(index=385, files=["385-tasks.create-a-pr-with-a-good-message.md"])],
    )

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.design_file is not None
    assert result.slice.task_items is None
    assert any("task file" in record.message for record in caplog.records)


def test_unreadable_design_degrades_to_absent_text_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    design_file = "project-documents/user/slices/385-slice.gone.md"
    cf_client = _cf_client(
        slices=[
            SliceEntry(
                index=385,
                name="Create a PR with a Good Message",
                design_file=design_file,
                status="not_started",
            )
        ],
        tasks=[],
    )

    with caplog.at_level("WARNING", logger="squadron.pr.inputs"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.design_file == design_file
    assert result.slice.design_text is None
    assert any(design_file in record.getMessage() for record in caplog.records)


def test_ancestor_of_head_but_outside_range_is_not_selected(git_repo: Path) -> None:
    """The load-bearing case: range membership, not ancestry of head."""
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)

    ancestor_sha = commit(git_repo, "a.txt", "prior slice work")
    (reviews_dir / "300-review.slice.prior-slice.md").write_text(
        f"---\nreviewedSha: {ancestor_sha}\nverdict: PASS\n---\n\nAn earlier, merged slice.\n"
    )
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)

    in_range_sha = commit(git_repo, "b.txt", "this slice's own work")
    (reviews_dir / "385-review.slice.this-slice.md").write_text(
        f"---\nreviewedSha: {in_range_sha}\nverdict: CONCERNS\n---\n\nThis slice's own review.\n"
    )

    result = find_latest_in_range_review(
        base="base-branch",
        head="main",
        cwd=str(git_repo),
        host=HOST,
        owner=OWNER,
        repository=REPOSITORY,
    )

    assert result is not None
    assert result.reviewed_sha == in_range_sha
    assert result.verdict == Verdict.CONCERNS


def test_no_reviews_at_all_returns_none(git_repo: Path) -> None:
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)

    result = find_latest_in_range_review(
        base="main", head="main", cwd=str(git_repo), host=HOST, owner=OWNER, repository=REPOSITORY
    )

    assert result is None


@pytest.mark.parametrize(
    "name",
    [
        "pr-83-review.code.md",
        "pr-83-review.code.ecorkran-squadron.md",
        "github.com-ecorkran-squadron-83-review.code.md",
    ],
)
def test_discovery_glob_finds_every_pr_review_name_form(git_repo: Path, name: str) -> None:
    """Both slice-926 forms and the older form are discovered (926, D5).

    The slice plan assumed ``*-review.*.md`` missed ``pr-83-review.code.md``; it
    does not. Driven through the real scan rather than a copied pattern, so a
    future tightening of the glob in ``inputs.py`` fails here instead of silently
    dropping PR review provenance from ``sq pr create``.
    """
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)
    reviewed_sha = commit(git_repo, "a.txt", "pr work")
    (reviews_dir / name).write_text(f"---\nreviewedSha: {reviewed_sha}\nverdict: PASS\n---\n")

    result = find_latest_in_range_review(
        base="base-branch",
        head="main",
        cwd=str(git_repo),
        host=HOST,
        owner=OWNER,
        repository=REPOSITORY,
    )

    assert result is not None
    assert result.path.name == name


def test_two_in_range_reviews_the_newer_sha_wins(git_repo: Path) -> None:
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, check=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)

    older_sha = commit(git_repo, "a.txt", "older work")
    (reviews_dir / "385-review.tasks.older.md").write_text(
        f"---\nreviewedSha: {older_sha}\nverdict: PASS\n---\n\nOlder review.\n"
    )
    newer_sha = commit(git_repo, "b.txt", "newer work")
    (reviews_dir / "385-review.slice.newer.md").write_text(
        f"---\nreviewedSha: {newer_sha}\nverdict: CONCERNS\n---\n\nNewer review.\n"
    )

    result = find_latest_in_range_review(
        base="base-branch",
        head="main",
        cwd=str(git_repo),
        host=HOST,
        owner=OWNER,
        repository=REPOSITORY,
    )

    assert result is not None
    assert result.reviewed_sha == newer_sha
    assert base_sha != newer_sha


def test_review_with_no_reviewed_sha_is_skipped_with_warning(
    git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)
    commit(git_repo, "a.txt", "some work")
    (reviews_dir / "385-review.slice.no-sha.md").write_text("---\nverdict: PASS\n---\n\nNo sha here.\n")

    with caplog.at_level("WARNING"):
        result = find_latest_in_range_review(
            base="base-branch",
            head="main",
            cwd=str(git_repo),
            host=HOST,
            owner=OWNER,
            repository=REPOSITORY,
        )

    assert result is None
    assert any("no-sha" in record.message for record in caplog.records)


def test_malformed_frontmatter_is_skipped_with_warning(
    git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)
    commit(git_repo, "a.txt", "some work")
    (reviews_dir / "385-review.slice.malformed.md").write_text("not even frontmatter\n")

    with caplog.at_level("WARNING"):
        result = find_latest_in_range_review(
            base="base-branch",
            head="main",
            cwd=str(git_repo),
            host=HOST,
            owner=OWNER,
            repository=REPOSITORY,
        )

    assert result is None
    assert any("malformed" in record.message for record in caplog.records)


def test_external_reviews_dir_used_when_no_project_documents(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No project-documents/ in the repo: falls through to the configured external dir."""
    external_dir = git_repo.parent / "external-reviews"
    external_dir.mkdir()
    subprocess.run(["git", "branch", "base-branch"], cwd=git_repo, capture_output=True, check=True)
    sha = commit(git_repo, "a.txt", "unplanned repo's own work")
    (external_dir / "1-review.pr.unplanned.md").write_text(
        f"---\nreviewedSha: {sha}\nverdict: PASS\n---\n\nExternal review.\n"
    )

    def _fake_resolve_reviews_dir(**_kwargs: object) -> tuple[Path, None]:
        return external_dir, None

    monkeypatch.setattr("squadron.pr.inputs.resolve_reviews_dir", _fake_resolve_reviews_dir)
    result = find_latest_in_range_review(
        base="base-branch",
        head="main",
        cwd=str(git_repo),
        host=HOST,
        owner=OWNER,
        repository=REPOSITORY,
    )

    assert result is not None
    assert result.reviewed_sha == sha


def test_cf_unavailable_entirely_degrades_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf_client = MagicMock()
    cf_client.list_slices.side_effect = ContextForgeNotAvailable("cf not on PATH")

    with caplog.at_level("WARNING"):
        result = gather_commits_and_slice(cf_client, base="main", head=SLICE_BRANCH, cwd=str(tmp_path))

    assert result.slice.index == 385
    assert result.slice.design_file is None
    assert result.slice.task_items is None
    assert any("385" in record.message for record in caplog.records)


def test_empty_commit_range_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A head with nothing the base lacks has no PR to open — refused, not degraded."""
    monkeypatch.setattr("squadron.pr.inputs.commits_in_range", lambda base, head, *, cwd: [])
    cf_client = _cf_client(slices=[], tasks=[])

    with pytest.raises(EmptyCommitRangeError, match=NON_SLICE_BRANCH):
        gather_commits_and_slice(cf_client, base="main", head=NON_SLICE_BRANCH, cwd=str(tmp_path))

    cf_client.list_slices.assert_not_called()


def test_review_scan_raises_when_the_range_does_not_resolve(git_repo: Path) -> None:
    """An unresolvable base must not read as "no review covers these commits"."""
    reviews_dir = git_repo / "project-documents" / "user" / "reviews"
    reviews_dir.mkdir(parents=True)

    with pytest.raises(GitRangeUnavailableError, match="no-such-base"):
        find_latest_in_range_review(
            base="no-such-base",
            head="main",
            cwd=str(git_repo),
            host=HOST,
            owner=OWNER,
            repository=REPOSITORY,
        )
