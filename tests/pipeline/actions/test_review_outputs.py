"""Tests for the review action's output keys and typed readers."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.review_outputs import (
    FINDING_INPUT_FILE,
    ReviewOutputKey,
    finding_input_file,
    review_file,
    review_input_files,
    unsaved_parts,
)
from squadron.pipeline.models import ActionResult


def _result(**outputs: object) -> ActionResult:
    return ActionResult(success=True, action_type=ActionType.REVIEW, outputs=dict(outputs))


def test_single_part_keys_keep_legacy_values() -> None:
    assert ReviewOutputKey.RESPONSE == "response"
    assert ReviewOutputKey.INPUT_FILE == "input_file"
    assert ReviewOutputKey.REVIEW_FILE == "review_file"
    assert FINDING_INPUT_FILE == "input_file"


class TestReviewInputFiles:
    def test_absent(self) -> None:
        assert review_input_files(_result()) == []

    def test_single(self) -> None:
        assert review_input_files(_result(input_file="a.md")) == ["a.md"]

    def test_multi(self) -> None:
        assert review_input_files(_result(input_files=["a.md", "b.md"])) == ["a.md", "b.md"]

    def test_prefers_input_files_over_input_file(self) -> None:
        result = _result(input_file="b.md", input_files=["a.md", "b.md"])
        assert review_input_files(result) == ["a.md", "b.md"]

    @pytest.mark.parametrize(
        "outputs",
        [{"input_files": "a.md"}, {"input_files": ["a.md", 3]}, {"input_file": 3}],
    )
    def test_wrong_shape_raises(self, outputs: dict[str, object]) -> None:
        with pytest.raises(TypeError):
            review_input_files(_result(**outputs))


class TestReviewFile:
    def test_absent(self) -> None:
        assert review_file(_result()) is None

    def test_present(self) -> None:
        assert review_file(_result(review_file="r.md")) == "r.md"

    def test_wrong_shape_raises(self) -> None:
        with pytest.raises(TypeError):
            review_file(_result(review_file=["r.md"]))


class TestUnsavedParts:
    def test_absent(self) -> None:
        assert unsaved_parts(_result()) == []

    def test_present(self) -> None:
        assert unsaved_parts(_result(unsaved_parts=["b.md"])) == ["b.md"]

    @pytest.mark.parametrize("value", ["b.md", [None]])
    def test_wrong_shape_raises(self, value: object) -> None:
        with pytest.raises(TypeError):
            unsaved_parts(_result(unsaved_parts=value))


class TestFindingInputFile:
    def test_absent(self) -> None:
        assert finding_input_file({"summary": "x"}) is None

    def test_present(self) -> None:
        assert finding_input_file({FINDING_INPUT_FILE: "a.md"}) == "a.md"

    def test_wrong_shape_raises(self) -> None:
        with pytest.raises(TypeError):
            finding_input_file({FINDING_INPUT_FILE: 7})
