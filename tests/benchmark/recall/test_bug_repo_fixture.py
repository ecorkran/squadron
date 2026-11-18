"""The fixture bug repo builds the history walkthrough step 5 needs."""

from __future__ import annotations

from tests.benchmark.recall.fixtures.bug_repo.build import BUG_FILE, BuiltBugRepo
from tests.conftest import run_test_git


def test_fixture_history(bug_repo: BuiltBugRepo) -> None:
    count = run_test_git(bug_repo.repo, "rev-list", "--count", f"{bug_repo.base}..{bug_repo.head}")
    assert count.strip() == "1"
    changed = run_test_git(bug_repo.repo, "show", "--name-only", "--format=", bug_repo.fix)
    assert changed.split() == [BUG_FILE]
    assert bug_repo.fix in bug_repo.case_file.read_text()
