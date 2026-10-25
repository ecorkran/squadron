"""Python duplication through the stdlib tokenizer (slice 401, D3)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.metrology.snapshot import duplication
from squadron.metrology.snapshot.python_adapter import measure_lengths, measure_python_duplication
from squadron.metrology.snapshot_models import AbsenceReason, Measurement, SnapshotMetric
from tests.metrology.snapshot.builders import make_context
from tests.metrology.snapshot.conftest import FakeToolRunner

STATEMENTS = 20  # about 8 tokens each: comfortably over the 100-token window


def function_source(name: str, comment: str, *, blank_lines: bool) -> str:
    body = []
    for index in range(STATEMENTS):
        body.append(f"    value_{index} = compute({index}, {index + 1})  # {comment}")
        if blank_lines:
            body.append("")
    return f"# {comment}\ndef {name}():\n" + "\n".join(body) + "\n"


def measure(repo: Path, files: dict[str, str]) -> dict[SnapshotMetric, Measurement]:
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    ctx = make_context(repo, FakeToolRunner())
    measured = {m.metric: m for m in measure_lengths(ctx, list(files))}
    measured[SnapshotMetric.DUPLICATED_LINES] = measure_python_duplication(ctx, list(files))
    return measured


def test_identical_function_reports_its_lines_despite_comments_and_blank_lines(
    tmp_path: Path,
) -> None:
    measured = measure(
        tmp_path,
        {
            "a.py": function_source("same", "first", blank_lines=False),
            "b.py": function_source("same", "second, longer comment", blank_lines=True),
        },
    )

    duplicated = measured[SnapshotMetric.DUPLICATED_LINES]
    # The def line plus one line per statement; comments and blank lines hold no tokens.
    assert duplicated.per_file == {"a.py": STATEMENTS + 1, "b.py": STATEMENTS + 1}
    assert duplicated.tool is not None
    assert duplicated.tool.name == "squadron-python-ast"
    assert "type-1" in duplicated.tool.counting


def test_renaming_the_function_still_matches_the_windows_after_the_name(tmp_path: Path) -> None:
    measured = measure(
        tmp_path,
        {
            "a.py": function_source("one", "c", blank_lines=False),
            "b.py": function_source("two", "c", blank_lines=False),
        },
    )

    # Windows that include the differing name don't match; the window starting at the
    # parenthesis after it does, so the def line is still covered along with the body.
    assert measured[SnapshotMetric.DUPLICATED_LINES].per_file == {
        "a.py": STATEMENTS + 1,
        "b.py": STATEMENTS + 1,
    }


@pytest.mark.parametrize(
    ("name", "source"),
    [
        ("unterminated.py", 'x = """never closed\n'),
        ("indent.py", "def f():\n        x = 1\n    y = 2\n"),
    ],
)
def test_tokenizer_failure_is_unparsed_for_duplication_and_keeps_file_length(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, name: str, source: str
) -> None:
    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {name: source})

    assert measured[SnapshotMetric.DUPLICATED_LINES].unparsed_files == [name]
    assert name in measured[SnapshotMetric.FILE_LENGTH].per_file
    assert f"Can't tokenize {name}" in caplog.text


def test_ceiling_fails_duplication_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(duplication, "DUPLICATION_MAX_TOKENS", 10)

    with caplog.at_level(logging.WARNING):
        measured = measure(tmp_path, {"a.py": function_source("same", "c", blank_lines=False)})

    assert measured[SnapshotMetric.DUPLICATED_LINES].absent is AbsenceReason.TOOL_FAILED
    assert "ceiling of 10" in caplog.text
    for metric in (
        SnapshotMetric.FILE_LENGTH,
        SnapshotMetric.FUNCTION_LENGTH,
    ):
        assert measured[metric].absent is None
    assert measured[SnapshotMetric.FILE_LENGTH].per_file == {"a.py": STATEMENTS + 2}
