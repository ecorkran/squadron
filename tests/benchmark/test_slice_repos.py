"""Each slice-repo builder produces the history shape its docstring names (slice 426, Task 6)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.benchmark.slice_repos import (
    DEVLOG,
    NEW_TEST_FILE,
    REAL_LANDING_SLICES,
    SOURCE_FILE,
    TEST_FILE,
    SliceRepo,
    all_tests_rewritten,
    branch_with_target_merge,
    design_path,
    docs_only_slice,
    fast_forward_landing,
    load_real_landings,
    no_design_at_fork,
    no_slice_plan_at_fork,
    no_task_file_at_fork,
    plan_path,
    split_task_files_at_fork,
    tasks_path,
    two_landings_of_one_slice,
    two_parent_landing,
)
from tests.conftest import run_test_git


def _parents(built: SliceRepo, sha: str) -> list[str]:
    return run_test_git(built.repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]


def _files_at(built: SliceRepo, sha: str) -> set[str]:
    return set(run_test_git(built.repo, "ls-tree", "-r", "--name-only", sha).split())


def _changed(built: SliceRepo) -> dict[str, str]:
    """``git diff --name-status fork tip`` as path -> status letter."""
    lines = run_test_git(
        built.repo, "diff", "--name-status", built.landing.fork, built.landing.tip
    ).splitlines()
    return {line.split("\t")[-1]: line[0] for line in lines}


def _check_two_parent(built: SliceRepo) -> None:
    landing = built.landing
    assert landing.merge == landing.after
    assert len(_parents(built, landing.after)) == 2
    assert _parents(built, landing.after) == [landing.before, landing.tip]


def _check_fast_forward(built: SliceRepo) -> None:
    landing = built.landing
    assert landing.merge is None
    assert landing.after == landing.tip
    assert run_test_git(built.repo, "rev-list", "--merges", f"{landing.fork}..{landing.tip}") == ""
    assert run_test_git(built.repo, "rev-parse", "main").strip() == landing.tip


def _check_two_landings(built: SliceRepo) -> None:
    assert built.second is not None
    merges = run_test_git(built.repo, "rev-list", "--merges", "main").split()
    assert set(merges) == {built.landing.after, built.second.after}
    assert built.second.fork == built.landing.tip


def _check_branch_with_merge(built: SliceRepo) -> None:
    landing = built.landing
    merges = run_test_git(built.repo, "rev-list", "--merges", f"{landing.fork}..{landing.tip}")
    assert len(merges.split()) == 1


def _check_no_task_file(built: SliceRepo) -> None:
    files = _files_at(built, built.landing.fork)
    assert design_path(built.index) in files
    assert plan_path() in files
    assert not any("/tasks/" in path for path in files)


def _check_no_design(built: SliceRepo) -> None:
    files = _files_at(built, built.landing.fork)
    assert tasks_path(built.index) in files
    assert plan_path() in files
    assert not any("/slices/" in path for path in files)


def _check_no_plan(built: SliceRepo) -> None:
    files = _files_at(built, built.landing.fork)
    assert design_path(built.index) in files
    assert tasks_path(built.index) in files
    assert plan_path() not in files


def _check_split_tasks(built: SliceRepo) -> None:
    files = _files_at(built, built.landing.fork)
    assert {tasks_path(built.index, suffix) for suffix in ("-1", "-2", "-10")} <= files
    assert tasks_path(built.index) not in files


def _check_docs_only(built: SliceRepo) -> None:
    changed = _changed(built)
    assert DEVLOG in changed
    assert SOURCE_FILE not in changed
    assert all(path == DEVLOG or path.startswith("project-documents/user/") for path in changed)


def _check_all_tests_rewritten(built: SliceRepo) -> None:
    changed = _changed(built)
    assert changed[TEST_FILE] == "M"
    fork_tests = {p for p in _files_at(built, built.landing.fork) if p.startswith("tests/")}
    assert fork_tests == {TEST_FILE}
    assert NEW_TEST_FILE not in changed


_SHAPES: list[tuple[Callable[[Path], SliceRepo], Callable[[SliceRepo], None]]] = [
    (two_parent_landing, _check_two_parent),
    (fast_forward_landing, _check_fast_forward),
    (two_landings_of_one_slice, _check_two_landings),
    (branch_with_target_merge, _check_branch_with_merge),
    (no_task_file_at_fork, _check_no_task_file),
    (no_design_at_fork, _check_no_design),
    (no_slice_plan_at_fork, _check_no_plan),
    (split_task_files_at_fork, _check_split_tasks),
    (docs_only_slice, _check_docs_only),
    (all_tests_rewritten, _check_all_tests_rewritten),
]


@pytest.mark.parametrize(("build", "check"), _SHAPES, ids=[build.__name__ for build, _ in _SHAPES])
def test_builder_produces_its_history_shape(
    tmp_path: Path,
    build: Callable[[Path], SliceRepo],
    check: Callable[[SliceRepo], None],
) -> None:
    built = build(tmp_path)

    # Every builder records real shas: the fork is an ancestor of the tip.
    run_test_git(built.repo, "merge-base", "--is-ancestor", built.landing.fork, built.landing.tip)
    check(built)


def test_real_landings_hold_one_landing_of_each_method() -> None:
    ranges = load_real_landings()

    methods = {
        index: [landing.method.value for landing in found] for index, found in ranges.slices.items()
    }
    assert methods == {index: [method] for index, method in REAL_LANDING_SLICES.items()}
    merge = ranges.slices[402][0]
    assert merge.merge_sha == merge.after_sha
    fast_forward = ranges.slices[420][0]
    assert fast_forward.merge_sha is None
    assert fast_forward.after_sha == fast_forward.tip_sha
