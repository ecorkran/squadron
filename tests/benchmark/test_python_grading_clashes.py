"""Injection clashes and filename collisions (slice 425 Task 18, D3)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.grading_adapter import InjectionResult
from squadron.benchmark.python_injection import ClashKind, clash, inject_hidden
from tests.benchmark.grading_fixtures import (
    HIDDEN_FILE,
    GradingRepo,
    build_variant,
    make_grading_case,
    run_pytest_ids,
)

INJECTED_FILE = "tests/review/test_sqhidden_test_parts.py"
SAME_NAME_TEST = "TestWorstVerdict::test_fail_outranks_unknown"
PRODUCER_FIXTURE_TEST = f"{HIDDEN_FILE}::TestWorstVerdict::test_producer_fixture_value"
FIXTURE_USING_TEST = "TestWorstVerdict::test_fold_matches_the_fixture_order"


def inject(grading_repo: GradingRepo, variant: str, tmp_path: Path) -> tuple[Path, InjectionResult]:
    tree = build_variant(grading_repo, variant, tmp_path / variant).root
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    return tree, result


def test_a_same_name_test_runs_on_both_sides_independently(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree, result = inject(grading_repo, "producer_d", tmp_path)
    producer_id = f"{HIDDEN_FILE}::{SAME_NAME_TEST}"
    hidden_id = f"{INJECTED_FILE}::{SAME_NAME_TEST}"
    assert clash(ClashKind.SAME_TEST_NAME, producer_id) in result.clashes
    assert dict(result.id_map)[producer_id] == hidden_id

    both = run_pytest_ids(tree, (producer_id, hidden_id))
    assert both == {producer_id: "passed", hidden_id: "passed"}

    injected = tree / INJECTED_FILE
    text = injected.read_text(encoding="utf-8")
    broken = 'assert worst_verdict(["FAIL", "UNKNOWN"]) == "UNKNOWN"'
    assert 'assert worst_verdict(["FAIL", "UNKNOWN"]) == "FAIL"' in text
    injected.write_text(
        text.replace('assert worst_verdict(["FAIL", "UNKNOWN"]) == "FAIL"', broken), encoding="utf-8"
    )
    assert run_pytest_ids(tree, (producer_id, hidden_id)) == {
        producer_id: "passed",
        hidden_id: "failed",
    }


def test_a_same_name_fixture_is_shadowed_for_the_injected_module_only(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree, result = inject(grading_repo, "producer_d", tmp_path)
    assert (
        clash(ClashKind.SAME_FIXTURE_NAME, "tests/review/conftest.py::verdict_order") in result.clashes
    )

    hidden_id = f"{INJECTED_FILE}::{FIXTURE_USING_TEST}"
    outcomes = run_pytest_ids(tree, (hidden_id, PRODUCER_FIXTURE_TEST))
    # The injected module sees the hidden fixture's Verdict list (the producer's ["producer"]
    # would make worst_verdict raise); the producer's module sees the producer's value.
    assert outcomes == {hidden_id: "passed", PRODUCER_FIXTURE_TEST: "passed"}


def test_a_taken_sibling_name_becomes_2_with_the_rename_in_clashes_and_the_id_map(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree, result = inject(grading_repo, "producer_e", tmp_path)
    renamed = "tests/review/test_sqhidden_test_parts_2.py"
    assert result.files_written == (renamed,)
    assert clash(ClashKind.FILENAME_TAKEN, f"{INJECTED_FILE} -> {renamed}") in result.clashes
    assert all(mapped.startswith(renamed) for _, mapped in result.id_map)
    assert (tree / INJECTED_FILE).read_text(encoding="utf-8").startswith('"""A file the producer')

    mapped = tuple(mapped_id for _, mapped_id in result.id_map)
    assert set(run_pytest_ids(tree, mapped).values()) == {"passed"}


def test_a_second_collision_gives_3(grading_repo: GradingRepo, tmp_path: Path) -> None:
    tree = build_variant(grading_repo, "producer_e", tmp_path / "e").root
    (tree / "tests/review/test_sqhidden_test_parts_2.py").write_text("X = 1\n", encoding="utf-8")
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    assert result.files_written == ("tests/review/test_sqhidden_test_parts_3.py",)
    assert (tree / "tests/review/test_sqhidden_test_parts_2.py").read_text(
        encoding="utf-8"
    ) == "X = 1\n"


def test_clash_lines_are_stable_text_the_report_can_count_by_kind(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    _, result = inject(grading_repo, "producer_d", tmp_path)
    kinds = [line.split(": ", 1)[0] for line in result.clashes]
    assert set(kinds) <= {kind.value for kind in ClashKind}
    assert kinds.count(ClashKind.SAME_TEST_NAME.value) >= 1
    assert kinds.count(ClashKind.SAME_FIXTURE_NAME.value) == 1


def test_an_untouched_producer_file_clashes_on_the_tests_it_already_had(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    """A hidden test that already exists at the start is a same-name clash by D3's rule."""
    tree = build_variant(grading_repo, "producer_a", tmp_path / "a").root
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    parametrized = clash(
        ClashKind.SAME_TEST_NAME, f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair"
    )
    assert parametrized in result.clashes
    assert clash(ClashKind.SAME_TEST_NAME, f"{HIDDEN_FILE}::{SAME_NAME_TEST}") not in result.clashes


def test_a_producer_test_file_that_is_not_utf8_records_no_clash_and_does_not_raise(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_d", tmp_path / "producer_d").root
    (tree / HIDDEN_FILE).write_bytes(b"def test_x():\n    assert '\xff\xfe'\n")
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    assert not any(SAME_NAME_TEST in entry for entry in result.clashes)
