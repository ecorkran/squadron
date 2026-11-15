"""Suppression counting from a diff (slice 425 Task 16, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.python_suppressions import count_suppressions
from squadron.metrology.grade_models import SuppressionCounts
from tests.benchmark.grading_fixtures import GradingRepo, build_variant


def diff_adding(
    path: str, *added: str, context: tuple[str, ...] = (), removed: tuple[str, ...] = ()
) -> bytes:
    body = (
        [f" {line}" for line in context]
        + [f"-{line}" for line in removed]
        + [f"+{line}" for line in added]
    )
    old = len(context) + len(removed)
    new = len(context) + len(added)
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,{old} +1,{new} @@",
        *body,
    ]
    return ("\n".join(lines) + "\n").encode()


def test_variant_b_gives_one_noqa_and_one_type_ignore_in_the_source_bucket(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    tree = build_variant(grading_repo, "producer_b", tmp_path / "b")
    assert count_suppressions(tree.diff()) == SuppressionCounts(noqa_source=1, type_ignore_source=1)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("x = 1  #noqa", SuppressionCounts(noqa_source=1)),
        ("x = 1  #  NOQA:E501,F401", SuppressionCounts(noqa_source=1)),
        ("x: int = 's'  # type:ignore[attr-defined]", SuppressionCounts(type_ignore_source=1)),
        ("x: int = 's'  # type: ignore", SuppressionCounts(type_ignore_source=1)),
        ("x = f()  # pyright: ignore[reportX]", SuppressionCounts(type_ignore_source=1)),
        (
            "x = f()  # noqa: E501  # type: ignore",
            SuppressionCounts(noqa_source=1, type_ignore_source=1),
        ),
        ("x = 1  # a comment, no marker", SuppressionCounts()),
        ("x = 1  # noqas is not a marker", SuppressionCounts()),
    ],
)
def test_lenient_markers_are_counted(line: str, expected: SuppressionCounts) -> None:
    assert count_suppressions(diff_adding("pkg/mod.py", line)) == expected


def test_removed_and_context_lines_do_not_count() -> None:
    diff = diff_adding(
        "pkg/mod.py",
        "clean = 1",
        context=("old = 1  # noqa",),
        removed=("gone = 2  # type: ignore",),
    )
    assert count_suppressions(diff) == SuppressionCounts()


def test_a_marker_in_a_header_path_does_not_count() -> None:
    diff = diff_adding("pkg/odd # noqa name.py", "clean = 1")
    assert count_suppressions(diff) == SuppressionCounts()


def test_a_plus_plus_plus_line_inside_a_hunk_is_an_added_line_not_a_header() -> None:
    diff = diff_adding("pkg/mod.py", "++ x = 1  # noqa")
    assert count_suppressions(diff) == SuppressionCounts(noqa_source=1)


def test_an_empty_diff_gives_zeros() -> None:
    assert count_suppressions(b"") == SuppressionCounts()


def test_a_test_file_addition_counts_under_test() -> None:
    diff = diff_adding(
        "tests/test_mod.py", "def test_x():  # noqa: D103", "    x: int = 's'  # type: ignore"
    )
    assert count_suppressions(diff) == SuppressionCounts(noqa_test=1, type_ignore_test=1)


def test_a_file_after_a_deleted_file_is_still_attributed_correctly() -> None:
    deleted = (
        b"diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n"
        b"@@ -1 +0,0 @@\n-x = 1  # noqa\n"
    )
    added = diff_adding("tests/test_new.py", "y = 2  # noqa")
    assert count_suppressions(deleted + added) == SuppressionCounts(noqa_test=1)
