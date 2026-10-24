"""Cobertura reader, freshness check and per-language measurements (slice 401, D4-D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.metrology.snapshot.coverage import (
    CoverageFailure,
    CoverageReading,
    read_cobertura,
)
from tests.metrology.snapshot.builders import read_fixture

REPORT = "cov.xml"
COVERAGEPY_FIXTURE = "cobertura_coveragepy.xml"
ISTANBUL_FIXTURE = "cobertura_istanbul.xml"
#: The root attributes of the captured coverage.py report.
COVERAGEPY_LINES_VALID = 1029
COVERAGEPY_LINES_COVERED = 501


def write_report(repo: Path, text: str) -> Path:
    report = repo / REPORT
    report.write_text(text, encoding="utf-8")
    return report


def read_report(repo: Path, text: str) -> CoverageReading | CoverageFailure:
    return read_cobertura(write_report(repo, text), REPORT, repo)


def read_ok(repo: Path, text: str) -> CoverageReading:
    result = read_report(repo, text)
    assert isinstance(result, CoverageReading), result
    return result


def read_failure(repo: Path, text: str) -> CoverageFailure:
    result = read_report(repo, text)
    assert isinstance(result, CoverageFailure), result
    return result


def minimal_report(lines: str = '<line number="1" hits="1"/>', version: str = ' version="1.0"') -> str:
    return (
        f"<coverage{version}><sources><source>__REPO_ROOT__</source></sources><packages><package>"
        f'<classes><class filename="a.py"><lines>{lines}</lines></class></classes>'
        "</package></packages></coverage>"
    )


class TestReadCobertura:
    def test_coveragepy_fixture_matches_the_report_totals(self, tmp_path: Path) -> None:
        reading = read_ok(tmp_path, read_fixture(COVERAGEPY_FIXTURE, tmp_path))

        assert reading.producer_version == "7.17.0"
        assert reading.report_path == REPORT
        assert "src/squadron/metrology/snapshot/lengths.py" in reading.files
        assert sum(len(f.coverable) for f in reading.files.values()) == COVERAGEPY_LINES_VALID
        assert sum(len(f.covered) for f in reading.files.values()) == COVERAGEPY_LINES_COVERED

    def test_istanbul_fixture_counts_class_lines_only(self, tmp_path: Path) -> None:
        reading = read_ok(tmp_path, read_fixture(ISTANBUL_FIXTURE, tmp_path))

        assert reading.producer_version == "0.1"
        # Method-level <line> entries (math.ts lines 1 and 5) are not in the root totals.
        assert reading.files["src/math.ts"].coverable == {2, 6, 7, 9}
        assert reading.files["src/math.ts"].covered == {2}
        assert reading.files["src/pure.ts"].coverable == {1}
        assert reading.files["src/pure.ts"].covered == frozenset()

    def test_a_repeated_line_entry_is_counted_once(self, tmp_path: Path) -> None:
        text = minimal_report('<line number="3" hits="0"/><line number="3" hits="2"/>').replace(
            "__REPO_ROOT__", str(tmp_path)
        )

        reading = read_ok(tmp_path, text)

        assert reading.files["a.py"].coverable == {3}
        assert reading.files["a.py"].covered == {3}

    def test_a_source_outside_the_repo_drops_its_classes(self, tmp_path: Path) -> None:
        text = minimal_report().replace("__REPO_ROOT__", "/somewhere/else")

        assert read_ok(tmp_path, text).files == {}

    @pytest.mark.parametrize(
        ("text", "problem"),
        [
            ("<coverage><unclosed>", "not well-formed XML"),
            ("<report/>", "not a Cobertura report"),
            (minimal_report(version=""), "no root version"),
            (minimal_report('<line number="1" hits="x"/>'), "non-integer"),
            (minimal_report('<line number="y" hits="1"/>'), "non-integer"),
            (minimal_report('<line number="1"/>'), "no hits attribute"),
        ],
    )
    def test_each_problem_is_a_failure_naming_the_report_and_the_problem(
        self, tmp_path: Path, text: str, problem: str
    ) -> None:
        failure = read_failure(tmp_path, text.replace("__REPO_ROOT__", str(tmp_path)))

        assert failure.report_path == REPORT
        assert REPORT in failure.detail
        assert problem in failure.detail

    def test_a_report_with_no_source_is_a_failure(self, tmp_path: Path) -> None:
        text = '<coverage version="1"><packages/></coverage>'

        assert "no <source>" in read_failure(tmp_path, text).detail

    def test_an_unreadable_report_is_a_failure(self, tmp_path: Path) -> None:
        result = read_cobertura(tmp_path / "missing.xml", "missing.xml", tmp_path)

        assert isinstance(result, CoverageFailure)
        assert "can't be read" in result.detail
