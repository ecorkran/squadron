"""Shared length-counting tests (slice 400, D1/D6)."""

from __future__ import annotations

import pytest

from squadron.metrology.snapshot.lengths import (
    FunctionLength,
    count_non_blank,
    count_non_blank_span,
    distribution,
    file_length_measurement,
    files_over_limit,
    function_length_measurement,
    physical_lines,
)
from squadron.metrology.snapshot_models import SourceLanguage, ToolIdentity

TOOL = ToolIdentity(name="counter", version="1", counting="non-blank lines")


class TestCounting:
    def test_blank_and_whitespace_only_lines_are_excluded(self) -> None:
        assert count_non_blank("a\n\n   \n\t\nb\n") == 2

    def test_all_line_ending_styles_count_alike(self) -> None:
        assert count_non_blank("a\r\nb\rc\n") == 3

    def test_trailing_newline_adds_no_line(self) -> None:
        assert physical_lines("a\nb\n") == ["a", "b"]
        assert physical_lines("a\nb") == ["a", "b"]
        assert physical_lines("") == []

    def test_form_feed_is_not_a_line_break(self) -> None:
        assert physical_lines("a\x0cb\n") == ["a\x0cb"]

    def test_span_is_one_based_and_inclusive(self) -> None:
        lines = ["a", "", "b", "  ", "c"]

        assert count_non_blank_span(lines, 1, 5) == 3
        assert count_non_blank_span(lines, 2, 4) == 1
        assert count_non_blank_span(lines, 3, 3) == 1


class TestDistribution:
    def test_one_value(self) -> None:
        result = distribution([7])

        assert result is not None
        assert (result.count, result.total, result.min, result.p50, result.p90, result.max) == (
            1,
            7,
            7,
            7,
            7,
            7,
        )

    def test_two_values_use_nearest_rank(self) -> None:
        result = distribution([20, 10])

        assert result is not None
        assert (result.min, result.p50, result.p90, result.max) == (10, 10, 20, 20)
        assert result.total == 30

    def test_ten_values(self) -> None:
        result = distribution(list(range(10, 110, 10)))

        assert result is not None
        assert (result.count, result.total) == (10, 550)
        assert (result.min, result.p50, result.p90, result.max) == (10, 50, 90, 100)

    def test_no_values_has_no_distribution_not_zeros(self) -> None:
        assert distribution([]) is None


class TestFileLength:
    def test_per_file_distribution_and_limit(self) -> None:
        measurement = file_length_measurement(
            SourceLanguage.PYTHON, TOOL, {"b.py": 400, "a.py": 10}, limit=300
        )

        assert list(measurement.per_file) == ["a.py", "b.py"]
        assert measurement.limit == 300
        assert measurement.distribution is not None
        assert measurement.distribution.max == 400

    def test_files_over_limit_returns_exactly_the_files_above_it(self) -> None:
        measurement = file_length_measurement(
            SourceLanguage.PYTHON, TOOL, {"a.py": 300, "b.py": 301, "c.py": 5}, limit=300
        )

        assert files_over_limit(measurement) == {"b.py": 301}

    def test_no_limit_means_nothing_is_over(self) -> None:
        measurement = file_length_measurement(SourceLanguage.PYTHON, TOOL, {"a.py": 9000}, limit=None)

        assert files_over_limit(measurement) == {}
        assert measurement.distribution is not None


class TestFunctionLength:
    FUNCTIONS = (
        FunctionLength("b.py", "g", 9, 70),
        FunctionLength("a.py", "f", 3, 50),
        FunctionLength("a.py", "Cls.m", 20, 51),
    )

    def test_over_limit_rows_only_above_the_limit(self) -> None:
        measurement = function_length_measurement(
            SourceLanguage.PYTHON, TOOL, self.FUNCTIONS, limit=50, unparsed_files=[]
        )

        assert [(row.path, row.qualified_name) for row in measurement.over_limit] == [
            ("a.py", "Cls.m"),
            ("b.py", "g"),
        ]
        assert measurement.distribution is not None
        assert measurement.distribution.count == 3

    def test_no_limit_gives_empty_over_limit_with_distribution_present(self) -> None:
        measurement = function_length_measurement(
            SourceLanguage.PYTHON, TOOL, self.FUNCTIONS, limit=None, unparsed_files=["bad.py"]
        )

        assert measurement.over_limit == []
        assert measurement.distribution is not None
        assert measurement.unparsed_files == ["bad.py"]

    def test_no_functions_is_present_with_no_distribution(self) -> None:
        measurement = function_length_measurement(
            SourceLanguage.PYTHON, TOOL, [], limit=50, unparsed_files=[]
        )

        assert measurement.absent is None
        assert measurement.distribution is None


@pytest.mark.parametrize("values", [[1, 2, 3, 4, 5], [5, 4, 3, 2, 1]])
def test_distribution_ignores_input_order(values: list[int]) -> None:
    assert distribution(values) == distribution(sorted(values))
