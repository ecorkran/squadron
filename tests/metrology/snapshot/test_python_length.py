"""Python adapter: ast length (slice 400, D6)."""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

import pytest

from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.python_adapter import PythonAdapter
from squadron.metrology.snapshot_models import (
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)
from tests.metrology.snapshot.conftest import FakeToolRunner


def context(
    repo: Path, *, max_file: int | None = None, max_function: int | None = None
) -> AdapterContext:
    return AdapterContext(
        repo_root=repo,
        limits=LengthLimits(
            max_file_lines=max_file,
            max_function_lines=max_function,
            limits_declared=max_file is not None or max_function is not None,
        ),
        runner=FakeToolRunner(),
        tool_timeout_s=5,
    )


def measure(
    repo: Path, files: dict[str, str | bytes], **limits: int | None
) -> dict[SnapshotMetric, Measurement]:
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(dedent(content), encoding="utf-8")
    result = PythonAdapter().measure(context(repo, **limits), list(files))
    return {m.metric: m for m in result}


def function_lengths(measurement: Measurement, path: str) -> dict[str, int]:
    """Qualified name -> length, read from over_limit rows (limit 0 is not allowed, so use 1)."""
    return {row.qualified_name: row.length for row in measurement.over_limit if row.path == path}


def test_adapter_declares_length_metrics_only_and_pb2_conventions() -> None:
    adapter = PythonAdapter()

    assert adapter.language is SourceLanguage.PYTHON
    assert adapter.metrics == {SnapshotMetric.FILE_LENGTH, SnapshotMetric.FUNCTION_LENGTH}
    assert adapter.convention_exclusions == ("**/*_pb2.py", "**/*_pb2_grpc.py")


def test_file_length_counts_non_blank_lines(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.py": "x = 1\n\n\ny = 2\n   \n"})

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"a.py": 2}


def test_decorated_function_spans_from_its_first_decorator(tmp_path: Path) -> None:
    source = """\
        import functools

        @functools.cache

        @functools.wraps(print)
        def decorated(a):
            # comment
            return a
    """
    measured = measure(tmp_path, {"a.py": source}, max_function=1)

    # Two decorators, def line, comment, return: the blank line between decorators is excluded.
    assert function_lengths(measured[SnapshotMetric.FUNCTION_LENGTH], "a.py") == {"decorated": 5}


def test_nested_and_method_qualnames(tmp_path: Path) -> None:
    source = """\
        class Outer:
            def method(self):
                def inner():
                    return 1
                return inner

            class Nested:
                async def amethod(self):
                    return 2

        def outer():
            def inner():
                return 3
            return inner
    """
    measured = measure(tmp_path, {"a.py": source}, max_function=1)

    assert set(function_lengths(measured[SnapshotMetric.FUNCTION_LENGTH], "a.py")) == {
        "Outer.method",
        "Outer.method.<locals>.inner",
        "Outer.Nested.amethod",
        "outer",
        "outer.<locals>.inner",
    }


def test_lambdas_are_excluded(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.py": "f = lambda x: x\nvalues = sorted([], key=lambda y: y)\n"})

    assert measured[SnapshotMetric.FUNCTION_LENGTH].distribution is None


def test_nested_function_counts_on_its_own_and_inside_its_parent(tmp_path: Path) -> None:
    source = """\
        def parent():
            x = 1

            def child():
                y = 2
                return y

            return child
    """
    measured = measure(tmp_path, {"a.py": source}, max_function=1)

    assert function_lengths(measured[SnapshotMetric.FUNCTION_LENGTH], "a.py") == {
        "parent": 6,
        "parent.<locals>.child": 3,
    }
    distribution = measured[SnapshotMetric.FUNCTION_LENGTH].distribution
    assert distribution is not None
    assert (distribution.count, distribution.total) == (2, 9)


def test_over_limit_rows_appear_only_above_the_limit(tmp_path: Path) -> None:
    source = """\
        def short():
            return 1

        def long():
            a = 1
            b = 2
            return a + b
    """
    measured = measure(tmp_path, {"a.py": source}, max_function=3)

    rows = measured[SnapshotMetric.FUNCTION_LENGTH].over_limit
    assert [(row.qualified_name, row.start_line, row.length) for row in rows] == [("long", 4, 4)]


def test_file_over_limit_is_reported_from_per_file(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"big.py": "x = 1\n" * 5, "small.py": "x = 1\n"}, max_file=3)

    measurement = measured[SnapshotMetric.FILE_LENGTH]
    assert measurement.limit == 3
    assert measurement.per_file == {"big.py": 5, "small.py": 1}


def test_syntax_error_file_keeps_file_length_and_is_listed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"bad.py": "def broken(:\n    pass\n", "ok.py": "x = 1\n"})

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"bad.py": 2, "ok.py": 1}
    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["bad.py"]
    assert any("bad.py" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_recursion_error_file_is_listed_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    deep = "x = " + "+".join(["1"] * 100_000) + "\n"

    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"deep.py": deep, "ok.py": "x = 1\n"})

    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["deep.py"]
    assert measured[SnapshotMetric.FILE_LENGTH].per_file["ok.py"] == 1
    assert any("deep.py" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_undecodable_bytes_keep_file_length_and_are_listed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"latin.py": b"\xff\xfe = 1\ny = 2\n"})

    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"latin.py": 2}
    assert measured[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["latin.py"]
    assert any("latin.py" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_unreadable_tracked_file_is_listed_and_not_measured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "dangling.py").symlink_to(tmp_path / "missing-target.py")

    with caplog.at_level(logging.WARNING):
        result = PythonAdapter().measure(context(tmp_path), ["dangling.py"])

    by_metric = {m.metric: m for m in result}
    assert by_metric[SnapshotMetric.FILE_LENGTH].per_file == {}
    assert by_metric[SnapshotMetric.FUNCTION_LENGTH].unparsed_files == ["dangling.py"]
    assert any("dangling.py" in r.getMessage() for r in caplog.records)


def test_tool_identity_names_the_in_process_counter(tmp_path: Path) -> None:
    measured = measure(tmp_path, {"a.py": "x = 1\n"})

    tool = measured[SnapshotMetric.FILE_LENGTH].tool
    assert tool is not None
    assert tool.name == "squadron-python-ast"
    assert "+python3." in tool.version
    assert "non-blank" in tool.counting
