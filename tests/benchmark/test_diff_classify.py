"""Diff classification before any sandbox exists (slice 422 D3, D4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

import pytest

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.diff_classify import (
    ChangeStatus,
    DiffClassification,
    DiffRejection,
    FileChange,
    classify_diff,
    parse_name_status,
)
from squadron.benchmark.fairness import (
    AllowedBoundary,
    CollectedTests,
    FairnessVerdict,
    FixCaseAdapter,
)
from squadron.metrology.benchmark_models import CandidateRejection, GraderCommand
from squadron.metrology.snapshot_models import SourceLanguage


class StubAdapter:
    """Satisfies ``FixCaseAdapter`` (pyright checks the assignment below); only the
    classification hooks do anything."""

    language = SourceLanguage.PYTHON

    def is_test_side(self, pyproject_text: str | None, path: str) -> bool:
        name = PurePosixPath(path).name
        return path.startswith("tests/") or name == "conftest.py" or name.startswith("test_")

    def is_test_source(self, path: str) -> bool:
        return path.endswith(".py")

    def lockfile_names(self) -> tuple[str, ...]:
        return ("uv.lock",)

    def collect(self, ctx: SandboxContext) -> CollectedTests:
        raise NotImplementedError

    def overlay(self, ctx: SandboxContext, files: Mapping[str, bytes | None]) -> None:
        raise NotImplementedError

    def boundary(self, ctx: SandboxContext) -> AllowedBoundary:
        raise NotImplementedError

    def trace(
        self, ctx: SandboxContext, node_ids: Sequence[str], allowed: AllowedBoundary
    ) -> Mapping[str, FairnessVerdict]:
        raise NotImplementedError

    def grader_commands(self, tree: Path) -> tuple[GraderCommand, ...]:
        raise NotImplementedError


ADAPTER: FixCaseAdapter = StubAdapter()

BASE_CONFTEST = """\
import pytest
from pathlib import Path


@pytest.fixture
def workdir(tmp_path):
    return tmp_path


LIMIT = 3
"""


def change(status: ChangeStatus, path: str) -> FileChange:
    return FileChange(status, path)


def classify(
    changes: list[FileChange],
    parent: dict[str, str] | None = None,
    reference: dict[str, str] | None = None,
) -> DiffClassification | DiffRejection:
    parent_files = parent or {}
    reference_files = reference or {}
    return classify_diff(
        changes,
        ADAPTER,
        None,
        lambda path: parent_files.get(path),
        lambda path: reference_files.get(path),
    )


def rejection_of(result: DiffClassification | DiffRejection) -> CandidateRejection:
    assert isinstance(result, DiffRejection)
    return result.rejection


def conftest_edit(new_text: str) -> DiffClassification | DiffRejection:
    return classify(
        [
            change(ChangeStatus.ADDED, "tests/test_new.py"),
            change(ChangeStatus.MODIFIED, "tests/conftest.py"),
        ],
        parent={"tests/conftest.py": BASE_CONFTEST},
        reference={"tests/conftest.py": new_text},
    )


# --- One case per reason --------------------------------------------------------


def test_a_source_only_diff_is_no_test_change() -> None:
    result = classify([change(ChangeStatus.MODIFIED, "src/pkg/mod.py")])
    assert rejection_of(result) is CandidateRejection.NO_TEST_CHANGE


def test_an_empty_diff_is_no_test_change() -> None:
    assert rejection_of(classify([])) is CandidateRejection.NO_TEST_CHANGE


def test_a_test_side_data_file_is_test_data_changed() -> None:
    result = classify(
        [
            change(ChangeStatus.ADDED, "tests/test_a.py"),
            change(ChangeStatus.ADDED, "tests/data/case.json"),
        ]
    )
    assert isinstance(result, DiffRejection)
    assert result.rejection is CandidateRejection.TEST_DATA_CHANGED
    assert "tests/data/case.json" in result.detail


def test_a_lockfile_in_the_diff_is_changes_lockfile() -> None:
    result = classify(
        [change(ChangeStatus.ADDED, "tests/test_a.py"), change(ChangeStatus.MODIFIED, "uv.lock")]
    )
    assert rejection_of(result) is CandidateRejection.CHANGES_LOCKFILE


def test_a_nested_lockfile_is_found_by_name() -> None:
    result = classify(
        [change(ChangeStatus.ADDED, "tests/test_a.py"), change(ChangeStatus.MODIFIED, "tools/uv.lock")]
    )
    assert rejection_of(result) is CandidateRejection.CHANGES_LOCKFILE


def test_a_clean_diff_is_classified_by_kind() -> None:
    result = classify(
        [
            change(ChangeStatus.ADDED, "tests/test_new.py"),
            change(ChangeStatus.MODIFIED, "tests/test_old.py"),
            change(ChangeStatus.DELETED, "tests/test_gone.py"),
            change(ChangeStatus.MODIFIED, "src/pkg/mod.py"),
        ]
    )
    assert result == DiffClassification(
        added=("tests/test_new.py",),
        changed=("tests/test_old.py", "src/pkg/mod.py"),
        deleted=("tests/test_gone.py",),
        test_side=("tests/test_new.py", "tests/test_old.py", "tests/test_gone.py"),
    )


def test_precedence_follows_the_documented_order() -> None:
    both = [
        change(ChangeStatus.ADDED, "tests/data/case.json"),
        change(ChangeStatus.MODIFIED, "uv.lock"),
        change(ChangeStatus.MODIFIED, "tests/conftest.py"),
    ]
    assert rejection_of(classify(both)) is CandidateRejection.TEST_DATA_CHANGED
    no_data = both[1:] + [change(ChangeStatus.ADDED, "tests/test_a.py")]
    assert rejection_of(classify(no_data)) is CandidateRejection.CHANGES_LOCKFILE
    only_support = [change(ChangeStatus.MODIFIED, "tests/conftest.py")]
    result = classify(only_support, parent={"tests/conftest.py": "x = 1\n"}, reference={})
    assert rejection_of(result) is CandidateRejection.MODIFIES_TEST_SUPPORT


# --- conftest.py (D3) -----------------------------------------------------------


def test_a_conftest_that_only_adds_a_fixture_and_an_import_passes() -> None:
    text = (
        "import os\n"
        + BASE_CONFTEST
        + "\n\n@pytest.fixture(scope='session')\ndef cache_dir():\n    return os.getcwd()\n"
    )
    assert isinstance(conftest_edit(text), DiffClassification)


def test_an_added_fixture_imported_by_bare_name_passes() -> None:
    parent = "from pytest import fixture\n\n\n@fixture\ndef one():\n    return 1\n"
    reference = parent + "\n\n@fixture\ndef two():\n    return 2\n"
    result = classify(
        [
            change(ChangeStatus.ADDED, "tests/test_new.py"),
            change(ChangeStatus.MODIFIED, "tests/conftest.py"),
        ],
        parent={"tests/conftest.py": parent},
        reference={"tests/conftest.py": reference},
    )
    assert isinstance(result, DiffClassification)


def test_a_changed_existing_fixture_body_fails() -> None:
    result = conftest_edit(BASE_CONFTEST.replace("return tmp_path", "return tmp_path / 'x'"))
    assert isinstance(result, DiffRejection)
    assert result.rejection is CandidateRejection.MODIFIES_TEST_SUPPORT
    assert "changed def workdir" in result.detail


def test_an_added_plain_helper_function_fails() -> None:
    result = conftest_edit(BASE_CONFTEST + "\n\ndef helper():\n    return 1\n")
    assert isinstance(result, DiffRejection)
    assert "added def helper" in result.detail


def test_an_added_class_or_constant_fails() -> None:
    assert rejection_of(conftest_edit(BASE_CONFTEST + "\n\nclass Thing:\n    pass\n")) is (
        CandidateRejection.MODIFIES_TEST_SUPPORT
    )
    assert rejection_of(conftest_edit(BASE_CONFTEST + "\nOTHER = 4\n")) is (
        CandidateRejection.MODIFIES_TEST_SUPPORT
    )


def test_a_changed_constant_and_a_removed_definition_fail() -> None:
    assert rejection_of(conftest_edit(BASE_CONFTEST.replace("LIMIT = 3", "LIMIT = 4"))) is (
        CandidateRejection.MODIFIES_TEST_SUPPORT
    )
    assert rejection_of(conftest_edit(BASE_CONFTEST.replace("LIMIT = 3\n", ""))) is (
        CandidateRejection.MODIFIES_TEST_SUPPORT
    )


def test_a_removed_import_fails() -> None:
    result = conftest_edit(BASE_CONFTEST.replace("from pathlib import Path\n", ""))
    assert isinstance(result, DiffRejection)
    assert "import was removed" in result.detail


def test_a_deleted_conftest_fails() -> None:
    result = classify(
        [
            change(ChangeStatus.ADDED, "tests/test_new.py"),
            change(ChangeStatus.DELETED, "tests/conftest.py"),
        ],
        parent={"tests/conftest.py": BASE_CONFTEST},
    )
    assert rejection_of(result) is CandidateRejection.MODIFIES_TEST_SUPPORT


def test_an_unparsable_conftest_names_the_syntax_error() -> None:
    result = conftest_edit("def broken(:\n")
    assert isinstance(result, DiffRejection)
    assert result.rejection is CandidateRejection.MODIFIES_TEST_SUPPORT
    assert "reference conftest.py does not parse" in result.detail
    parent_broken = classify(
        [
            change(ChangeStatus.ADDED, "tests/test_new.py"),
            change(ChangeStatus.MODIFIED, "tests/conftest.py"),
        ],
        parent={"tests/conftest.py": "def broken(:\n"},
        reference={"tests/conftest.py": BASE_CONFTEST},
    )
    assert isinstance(parent_broken, DiffRejection)
    assert "parent conftest.py does not parse" in parent_broken.detail


def test_an_added_conftest_is_not_a_modification() -> None:
    result = classify(
        [change(ChangeStatus.ADDED, "tests/conftest.py")],
        reference={"tests/conftest.py": BASE_CONFTEST},
    )
    assert isinstance(result, DiffClassification)


# --- name-status parsing --------------------------------------------------------


def test_parse_handles_each_status_and_renames_as_delete_plus_add() -> None:
    text = (
        "A\ttests/new.py\nM\tsrc/mod.py\nD\ttests/old.py\nR087\ttests/a.py\ttests/b.py\nT\tsrc/link\n"
    )
    assert parse_name_status(text) == (
        FileChange(ChangeStatus.ADDED, "tests/new.py"),
        FileChange(ChangeStatus.MODIFIED, "src/mod.py"),
        FileChange(ChangeStatus.DELETED, "tests/old.py"),
        FileChange(ChangeStatus.DELETED, "tests/a.py"),
        FileChange(ChangeStatus.ADDED, "tests/b.py"),
        FileChange(ChangeStatus.MODIFIED, "src/link"),
    )


def test_a_copy_is_only_an_add_because_its_source_stays() -> None:
    assert parse_name_status("C100\ttests/a.py\ttests/copy.py\n") == (
        FileChange(ChangeStatus.ADDED, "tests/copy.py"),
    )


def test_quoted_paths_are_unquoted_leniently() -> None:
    text = (
        'A\t"tests/with space \\"q\\".py"\nA\t"tests/caf\\303\\251.py"\nM\t  \n\nA\ttests/plain.py\r\n'
    )
    assert [c.path for c in parse_name_status(text)] == [
        'tests/with space "q".py',
        "tests/café.py",
        "tests/plain.py",
    ]


@pytest.mark.parametrize("text", ["", "\n", "garbage without a tab\n"])
def test_unreadable_lines_yield_no_changes(text: str) -> None:
    assert parse_name_status(text) == ()
