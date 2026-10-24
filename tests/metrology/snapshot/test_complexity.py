"""The complexity measurement beside function length, both languages (slice 401, D1, D2)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest

from squadron.metrology.snapshot.python_adapter import measure_lengths
from squadron.metrology.snapshot.typescript_length import measure_typescript_lengths
from squadron.metrology.snapshot_models import Measurement, SnapshotMetric, SourceLanguage
from tests.metrology.snapshot.builders import make_context
from tests.metrology.snapshot.conftest import FakeToolRunner

PYTHON_SOURCE = """\
    class Box:
        def open(self, x):
            if x:
                return [i for i in x if i]
            return None

        async def close(self):
            def inner(y):
                return y and 1
            return inner

    def top(a, b):
        return lambda z: a if z else b
"""

TYPESCRIPT_SOURCE = """\
    export class Box {
      open(x: any) {
        if (x) { return 1; }
        return x ?? 2;
      }
    }
    export const make = (a: any) => {
      const inner = () => {
        return a ? 1 : 2;
      };
      return inner;
    };
    export const short = (a: any) => a + 1;
"""

PYTHON_BROKEN = "def broken(:\n    pass\n"
TYPESCRIPT_BROKEN = "export function broken( {\n"


def write(repo: Path, files: dict[str, str]) -> list[str]:
    for name, content in files.items():
        (repo / name).write_text(dedent(content), encoding="utf-8")
    return list(files)


def python_metrics(
    repo: Path, files: dict[str, str], **limits: int
) -> dict[SnapshotMetric, Measurement]:
    ctx = make_context(repo, FakeToolRunner(), **limits)
    return {m.metric: m for m in measure_lengths(ctx, write(repo, files))}


def typescript_metrics(
    repo: Path, files: dict[str, str], **limits: int
) -> dict[SnapshotMetric, Measurement]:
    ctx = make_context(repo, FakeToolRunner(), **limits)
    return {m.metric: m for m in measure_typescript_lengths(ctx, write(repo, files))}


def both_languages(tmp_path: Path) -> list[tuple[SourceLanguage, dict[SnapshotMetric, Measurement]]]:
    python_repo = tmp_path / "py"
    ts_repo = tmp_path / "ts"
    python_repo.mkdir()
    ts_repo.mkdir()
    return [
        (SourceLanguage.PYTHON, python_metrics(python_repo, {"a.py": PYTHON_SOURCE}, max_function=1)),
        (
            SourceLanguage.TYPESCRIPT,
            typescript_metrics(ts_repo, {"a.ts": TYPESCRIPT_SOURCE}, max_function=1),
        ),
    ]


def test_complexity_covers_the_same_functions_as_function_length(tmp_path: Path) -> None:
    for _language, measured in both_languages(tmp_path):
        length = measured[SnapshotMetric.FUNCTION_LENGTH]
        complexity = measured[SnapshotMetric.CYCLOMATIC_COMPLEXITY]

        assert length.distribution is not None
        assert complexity.distribution is not None
        assert complexity.distribution.count == length.distribution.count
        assert complexity.distribution.count >= 3


def test_known_complexities_are_distributed(tmp_path: Path) -> None:
    python = python_metrics(tmp_path, {"a.py": PYTHON_SOURCE})[SnapshotMetric.CYCLOMATIC_COMPLEXITY]

    # open: 1 + if + comp for + comp if = 4; close: 1; inner: 1 + and = 2; top: 1 + ifexp = 2
    assert python.distribution is not None
    assert (python.distribution.count, python.distribution.total, python.distribution.max) == (4, 9, 4)


@pytest.mark.parametrize(
    ("measure", "source", "name", "broken"),
    [
        (python_metrics, PYTHON_SOURCE, "a.py", PYTHON_BROKEN),
        (typescript_metrics, TYPESCRIPT_SOURCE, "a.ts", TYPESCRIPT_BROKEN),
    ],
)
def test_parse_error_file_is_unparsed_in_both_measurements_only(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    measure: Callable[..., dict[SnapshotMetric, Measurement]],
    source: str,
    name: str,
    broken: str,
) -> None:
    bad = f"bad.{name.split('.')[1]}"
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {name: source, bad: broken})

    for metric in (SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.CYCLOMATIC_COMPLEXITY):
        assert measured[metric].unparsed_files == [bad]
    assert bad in measured[SnapshotMetric.FILE_LENGTH].per_file
    assert bad not in measured[SnapshotMetric.CYCLOMATIC_COMPLEXITY].per_file
    assert any(bad in record.getMessage() for record in caplog.records)


def test_recursion_error_marks_the_file_unparsed_for_both(tmp_path: Path) -> None:
    # A 5000-term sum nests 5000 BinOp nodes: deep enough to exhaust the walk's recursion.
    deep = "def g():\n    return " + " + ".join(["1"] * 5000) + "\n"
    measured = python_metrics(tmp_path, {"deep.py": deep})

    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["deep.py"]
    assert measured[SnapshotMetric.CYCLOMATIC_COMPLEXITY].unparsed_files == ["deep.py"]


def test_tool_name_matches_function_length_and_counting_differs(tmp_path: Path) -> None:
    for _language, measured in both_languages(tmp_path):
        length_tool = measured[SnapshotMetric.FUNCTION_LENGTH].tool
        complexity_tool = measured[SnapshotMetric.CYCLOMATIC_COMPLEXITY].tool

        assert length_tool is not None
        assert complexity_tool is not None
        assert complexity_tool.name == length_tool.name
        assert complexity_tool.version == length_tool.version
        assert complexity_tool.counting != length_tool.counting
        assert "McCabe" in complexity_tool.counting


def test_complexity_has_no_per_file_or_limit_even_with_a_function_limit(tmp_path: Path) -> None:
    for _language, measured in both_languages(tmp_path):
        complexity = measured[SnapshotMetric.CYCLOMATIC_COMPLEXITY]

        assert complexity.per_file == {}
        assert complexity.limit is None
        assert complexity.over_limit == []
        assert measured[SnapshotMetric.FUNCTION_LENGTH].limit == 1
