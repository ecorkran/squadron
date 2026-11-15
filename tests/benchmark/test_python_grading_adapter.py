"""``PythonGradingAdapter``: the composition and its registration (slice 425 Task 19)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.benchmark.python_grading import PythonGradingAdapter
from squadron.benchmark.registry import grading_adapter_for
from squadron.metrology.grade_models import SuppressionCounts
from squadron.metrology.snapshot_models import SourceLanguage
from tests.benchmark.grading_fixtures import (
    HIDDEN_FILE,
    GradingRepo,
    build_variant,
    make_grading_case,
)


def test_the_adapter_satisfies_the_protocol() -> None:
    assert isinstance(PythonGradingAdapter(), GradingAdapter)
    assert PythonGradingAdapter().language is SourceLanguage.PYTHON


def test_the_registry_returns_it_for_python() -> None:
    assert isinstance(grading_adapter_for(SourceLanguage.PYTHON), PythonGradingAdapter)


def test_one_pass_over_the_fixture_trees_calls_every_method_once(
    grading_repo: GradingRepo, tmp_path: Path
) -> None:
    variant = build_variant(grading_repo, "producer_d", tmp_path / "d")
    adapter = grading_adapter_for(SourceLanguage.PYTHON)

    assert adapter.restore_tool_config(variant.root, grading_repo.start).config_edits == ()
    assert adapter.deps_changed(variant.root, grading_repo.start) is False

    edits = adapter.test_side_edits(variant.root, grading_repo.start)
    assert HIDDEN_FILE in edits
    adapter.restore_test_files(variant.root, grading_repo.start, edits)
    assert adapter.test_side_edits(variant.root, grading_repo.start) == ()

    injected = adapter.inject_hidden(
        variant.root, make_grading_case(grading_repo), grading_repo.start, grading_repo.reference
    )
    assert injected.files_written == ("tests/review/test_sqhidden_test_parts.py",)
    assert (variant.root / injected.files_written[0]).is_file()

    counts = adapter.count_suppressions(variant.diff())
    assert counts == SuppressionCounts()
