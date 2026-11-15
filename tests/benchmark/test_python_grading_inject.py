"""Hidden-test injection as a sibling module (slice 425 Task 17, D3)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.python_injection import ClashKind, clash, inject_hidden
from tests.benchmark.grading_fixtures import (
    HIDDEN_FILE,
    HIDDEN_IDS,
    GradingRepo,
    build_variant,
    checkout_tree,
    collect_ids,
    make_grading_case,
    run_pytest_ids,
)

INJECTED_FILE = "tests/review/test_sqhidden_test_parts.py"
CONFTEST_IMPORT = "from collections.abc import Iterator, Sequence"


def injected_tree(grading_repo: GradingRepo, tmp_path: Path) -> Path:
    return checkout_tree(grading_repo, grading_repo.start_sha, tmp_path / "start-tree")


def test_the_mapped_ids_replace_only_the_file_part(grading_repo: GradingRepo, tmp_path: Path) -> None:
    tree = injected_tree(grading_repo, tmp_path)
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    parametrized = f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair[FAIL-UNKNOWN]"
    assert dict(result.id_map)[parametrized] == (
        f"{INJECTED_FILE}::TestWorstVerdict::test_every_ordered_pair[FAIL-UNKNOWN]"
    )
    assert sorted(original for original, _ in result.id_map) == sorted(HIDDEN_IDS)
    assert result.files_written == (INJECTED_FILE,)
    # The parametrized hidden test already exists in the start's file: D3's same-name clash.
    assert result.clashes == (
        clash(ClashKind.SAME_TEST_NAME, f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair"),
    )


def test_the_module_holds_the_import_then_the_reference_body_then_the_fixture(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = injected_tree(grading_repo, tmp_path)
    inject_hidden(tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference)
    module = (tree / INJECTED_FILE).read_text(encoding="utf-8")
    reference_body = grading_repo.reference.read(HIDDEN_FILE).decode()

    assert module.count(CONFTEST_IMPORT) == 1
    first_body_statement = module.index("import itertools")
    assert module.index("from __future__ import annotations") < module.index(CONFTEST_IMPORT)
    assert module.index(CONFTEST_IMPORT) < first_body_statement
    assert first_body_statement < module.index("class TestReviewParts")
    assert module.index("class TestWorstVerdict") < module.index("def verdict_order")
    assert "@pytest.fixture\ndef verdict_order" in module
    for line in reference_body.splitlines():
        assert line in module.splitlines()


def test_a_producer_file_in_the_same_directory_is_byte_identical_afterwards(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_a", tmp_path / "a").root
    before = (tree / HIDDEN_FILE).read_bytes()
    inject_hidden(tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference)
    assert (tree / HIDDEN_FILE).read_bytes() == before


def test_collect_on_the_injected_tree_returns_exactly_the_hidden_ids(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = injected_tree(grading_repo, tmp_path)
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    mapped = tuple(mapped_id for _, mapped_id in result.id_map)
    assert sorted(collect_ids(tree, mapped)) == sorted(mapped)


def test_the_injected_hidden_tests_pass_on_the_reference_environment(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = injected_tree(grading_repo, tmp_path)
    result = inject_hidden(
        tree, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    mapped = tuple(mapped_id for _, mapped_id in result.id_map)
    assert run_pytest_ids(tree, mapped) == {mapped_id: "passed" for mapped_id in mapped}


def test_a_case_with_no_hidden_tests_injects_nothing(grading_repo: GradingRepo, tmp_path: Path) -> None:
    tree = injected_tree(grading_repo, tmp_path)
    case = make_grading_case(grading_repo).model_copy(
        update={"hidden_tests": (), "hidden_fixtures": ()}
    )
    result = inject_hidden(tree, case, grading_repo.start, grading_repo.reference)
    assert (result.id_map, result.files_written, result.clashes) == ((), (), ())
    assert not (tree / INJECTED_FILE).exists()
