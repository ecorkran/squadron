"""The grading fixture trees and their pytest runner (slice 425 Tasks 12-13)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmark.grading_fixtures import (
    FIXTURE_ROOT,
    HIDDEN_FILE,
    HIDDEN_IDS,
    PARAMETRIZED_HIDDEN_ID,
    PRODUCER_VARIANT_FILES,
    GradingRepo,
    build_variant,
    checkout_tree,
    collect_ids,
    run_pytest_ids,
)


def test_the_builder_yields_two_distinct_commits(grading_repo: GradingRepo) -> None:
    assert grading_repo.start_sha != grading_repo.reference_sha
    assert len(grading_repo.start_sha) == len(grading_repo.reference_sha) == 40


def test_start_and_reference_test_files_differ(grading_repo: GradingRepo) -> None:
    assert grading_repo.start.read(HIDDEN_FILE) != grading_repo.reference.read(HIDDEN_FILE)


def test_the_reference_conftest_adds_imports_and_one_fixture(grading_repo: GradingRepo) -> None:
    start = grading_repo.start.read("tests/review/conftest.py").decode()
    reference = grading_repo.reference.read("tests/review/conftest.py").decode()
    assert "from collections.abc import Iterator, Sequence" in reference
    assert "from collections.abc import Iterator, Sequence" not in start
    assert "from squadron.review.models import Verdict" in reference
    assert "from squadron.review.models import Verdict" not in start
    assert reference.count("@pytest.fixture") == start.count("@pytest.fixture") + 1
    assert "def verdict_order" in reference
    assert "def verdict_order" not in start


def test_the_parametrized_hidden_id_has_the_class_method_param_shape() -> None:
    assert PARAMETRIZED_HIDDEN_ID == (
        f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair[FAIL-UNKNOWN]"
    )


def test_collect_ids_on_the_start_tree_returns_the_parametrized_id(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = checkout_tree(grading_repo, grading_repo.start_sha, tmp_path / "start-tree")
    assert collect_ids(tree, (PARAMETRIZED_HIDDEN_ID,)) == (PARAMETRIZED_HIDDEN_ID,)


def test_the_reference_tree_passes_every_hidden_id(grading_repo: GradingRepo, tmp_path: Path) -> None:
    tree = checkout_tree(grading_repo, grading_repo.reference_sha, tmp_path / "reference-tree")
    assert run_pytest_ids(tree, HIDDEN_IDS) == {hidden: "passed" for hidden in HIDDEN_IDS}


def test_a_one_line_edit_that_breaks_the_test_is_reported_failed(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = checkout_tree(grading_repo, grading_repo.reference_sha, tmp_path / "broken-tree")
    test_file = tree / HIDDEN_FILE
    original = "_ORDER = [Verdict.PASS, Verdict.CONCERNS, Verdict.UNKNOWN, Verdict.FAIL]"
    broken = "_ORDER = [Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL, Verdict.UNKNOWN]"
    text = test_file.read_text(encoding="utf-8")
    assert original in text
    test_file.write_text(text.replace(original, broken), encoding="utf-8")
    outcomes = run_pytest_ids(tree, (PARAMETRIZED_HIDDEN_ID,))
    assert outcomes == {PARAMETRIZED_HIDDEN_ID: "failed"}


@pytest.mark.parametrize("variant", sorted(PRODUCER_VARIANT_FILES))
def test_each_variant_builds_and_differs_from_the_start_only_in_its_files(
    grading_repo: GradingRepo, tmp_path: Path, variant: str
) -> None:
    tree = build_variant(grading_repo, variant, tmp_path / variant)
    assert tree.commit_sha != tree.start_sha
    assert tree.changed_files() == PRODUCER_VARIANT_FILES[variant]
    assert tree.diff().startswith(b"diff --git ")


def test_every_variant_directory_is_listed() -> None:
    on_disk = {path.name for path in FIXTURE_ROOT.glob("producer_*") if path.is_dir()}
    assert on_disk == set(PRODUCER_VARIANT_FILES)
