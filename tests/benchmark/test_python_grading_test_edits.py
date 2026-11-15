"""Test-side edit detection and restoration (slice 425 Task 15, D6).

``test_side_edits`` is reached through its module: imported by name into a test module,
pytest would collect it as a test.
"""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark import python_grading
from squadron.benchmark.python_grading import restore_test_files
from tests.benchmark.grading_fixtures import HIDDEN_FILE, GradingRepo, build_variant, checkout_tree

ORIGINAL_ASSERTION = 'ReviewPart("a-1.md", "part-1")'


def test_a_weakened_assertion_is_reported_and_restored(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_a", tmp_path / "a").root
    assert ORIGINAL_ASSERTION not in (tree / HIDDEN_FILE).read_text(encoding="utf-8")

    edits = python_grading.test_side_edits(tree, grading_repo.start)
    assert edits == (HIDDEN_FILE,)

    restore_test_files(tree, grading_repo.start, edits)
    assert ORIGINAL_ASSERTION in (tree / HIDDEN_FILE).read_text(encoding="utf-8")
    assert python_grading.test_side_edits(tree, grading_repo.start) == ()


def test_a_deleted_test_file_is_reported_and_recreated(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = checkout_tree(grading_repo, grading_repo.start_sha, tmp_path / "deleted")
    original = (tree / HIDDEN_FILE).read_bytes()
    (tree / HIDDEN_FILE).unlink()

    edits = python_grading.test_side_edits(tree, grading_repo.start)
    assert HIDDEN_FILE in edits

    restore_test_files(tree, grading_repo.start, edits)
    assert (tree / HIDDEN_FILE).read_bytes() == original


def test_a_new_test_file_is_neither_reported_nor_removed(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_e", tmp_path / "e").root
    added = tree / "tests/review/test_sqhidden_test_parts.py"
    assert python_grading.test_side_edits(tree, grading_repo.start) == ()
    restore_test_files(tree, grading_repo.start, ())
    assert added.exists()


def test_a_modified_non_test_file_is_not_reported(grading_repo: GradingRepo, tmp_path: Path) -> None:
    tree = build_variant(grading_repo, "producer_c", tmp_path / "c").root
    assert (tree / "pyproject.toml").read_bytes() != grading_repo.start.read("pyproject.toml")
    assert python_grading.test_side_edits(tree, grading_repo.start) == ()


def test_the_edited_conftest_is_reported_with_the_test_file(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_d", tmp_path / "d").root
    assert python_grading.test_side_edits(tree, grading_repo.start) == (
        "tests/review/conftest.py",
        HIDDEN_FILE,
    )
