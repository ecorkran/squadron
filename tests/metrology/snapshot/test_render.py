"""Summary rendering tests (slice 400)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.snapshot.lengths import (
    MeasuredFunction,
    file_length_measurement,
    function_length_measurement,
)
from squadron.metrology.snapshot.render import render_summary
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    CodeSnapshot,
    Distribution,
    EnvironmentIdentity,
    LanguageSnapshot,
    LengthLimits,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)
from tests.metrology.snapshot.builders import make_project_id

TOOL = ToolIdentity(name="tool", version="1.0", counting="counting")


def python_snapshot() -> CodeSnapshot:
    language = SourceLanguage.PYTHON
    measurements = [
        file_length_measurement(language, TOOL, {"a.py": 400, "b.py": 10}, limit=300),
        function_length_measurement(
            language, TOOL, [MeasuredFunction("a.py", "f", 1, 70, 1)], limit=50, unparsed_files=["c.py"]
        ),
        Measurement(
            metric=SnapshotMetric.LINT_COUNT,
            language=language,
            tool=ToolIdentity(name="ruff", version="0.15.1", counting="c"),
            rule_set=RuleSetIdentity(source="pyproject.toml[tool.ruff]", content_hash="a" * 64),
            per_file={"a.py": 2, "b.py": 1},
        ),
        Measurement(
            metric=SnapshotMetric.TYPE_ERRORS,
            language=language,
            absent=AbsenceReason.ENVIRONMENT_UNRESOLVED,
            absent_detail=".venv not found",
        ),
        *[
            Measurement(
                metric=metric,
                language=language,
                absent=AbsenceReason.TOOL_MISSING,
                absent_detail="not measured in this fixture",
            )
            for metric in (
                SnapshotMetric.CYCLOMATIC_COMPLEXITY,
                SnapshotMetric.DUPLICATED_LINES,
                SnapshotMetric.COVERED_LINES,
                SnapshotMetric.COVERABLE_LINES,
            )
        ],
    ]
    return CodeSnapshot(
        snapshot_id="snapshot-x-y",
        project_id=make_project_id(),
        commit_sha="c" * 40,
        measured_at=datetime(2026, 10, 22, tzinfo=UTC),
        squadron_version="0.23.8",
        limits=LengthLimits(max_file_lines=300, max_function_lines=50, limits_declared=True),
        exclusions=["a/**"],
        languages=[
            LanguageSnapshot(
                language=language, file_count=3, adapter="PythonAdapter", measurements=measurements
            )
        ],
    )


def test_summary_lines_cover_each_metric_limits_exclusions_and_record() -> None:
    lines = render_summary(python_snapshot(), Path("/store/snapshot-x-y.json"))
    text = "\n".join(lines)

    assert lines[0].startswith("snapshot of cccccccccccc")
    assert "python (3 file(s))" in text
    assert "file_length: 2 files, p50 10, p90 400, max 400; 1 over 300 [tool 1.0]" in text
    assert "function_length: 1 functions, p50 70, p90 70, max 70; 1 over 50; 1 unparsed" in text
    assert "lint_count: 3 in 2 file(s), rules pyproject.toml[tool.ruff] [ruff 0.15.1]" in text
    assert "type_errors: absent: environment_unresolved (.venv not found)" in text
    assert "limits: file 300, function 50" in lines
    assert "exclusions: 1" in lines
    assert lines[-1] == "record: /store/snapshot-x-y.json"


def test_environment_and_tool_ignored_files_are_shown() -> None:
    measurement = Measurement(
        metric=SnapshotMetric.TYPE_ERRORS,
        language=SourceLanguage.PYTHON,
        tool=ToolIdentity(name="pyright", version="1.1.408", counting="c"),
        rule_set=RuleSetIdentity(source="tool-defaults", content_hash=None),
        environment=EnvironmentIdentity(
            lockfile_path="uv.lock", lockfile_sha256="abcdef0123456789", interpreter_version="3.12"
        ),
        tool_ignored_files=["x.ts"],
        per_file={},
    )

    snapshot = python_snapshot()
    entry = snapshot.languages[0]
    entry.measurements = [m for m in entry.measurements if m.metric is not SnapshotMetric.TYPE_ERRORS]
    entry.measurements.append(measurement)

    text = "\n".join(render_summary(snapshot, Path("/r.json")))

    assert "type_errors: 0 in 0 file(s), rules tool-defaults, uv.lock abcdef01" in text
    assert "1 skipped by the tool's ignores" in text


def test_new_metrics_render_in_the_contract_shapes() -> None:
    language = SourceLanguage.PYTHON
    snapshot = python_snapshot()
    entry = snapshot.languages[0]
    new_metrics = {
        SnapshotMetric.CYCLOMATIC_COMPLEXITY,
        SnapshotMetric.DUPLICATED_LINES,
        SnapshotMetric.COVERED_LINES,
        SnapshotMetric.COVERABLE_LINES,
    }
    ast = ToolIdentity(name="squadron-python-ast", version="1", counting="c")
    cobertura = ToolIdentity(name="cobertura", version="7.17.0", counting="c")
    entry.measurements = [
        *(m for m in entry.measurements if m.metric not in new_metrics),
        Measurement(
            metric=SnapshotMetric.CYCLOMATIC_COMPLEXITY,
            language=language,
            tool=ast,
            distribution=Distribution(count=3, total=9, min=1, p50=2, p90=6, max=6),
            unparsed_files=["c.py"],
        ),
        Measurement(
            metric=SnapshotMetric.DUPLICATED_LINES,
            language=language,
            tool=ast,
            per_file={"a.py": 10, "b.py": 5},
        ),
        Measurement(
            metric=SnapshotMetric.COVERABLE_LINES,
            language=language,
            tool=cobertura,
            per_file={"a.py": 40},
            tool_ignored_files=["b.py", "c.py"],
        ),
        Measurement(
            metric=SnapshotMetric.COVERED_LINES,
            language=language,
            tool=cobertura,
            per_file={"a.py": 30},
            tool_ignored_files=["b.py", "c.py"],
        ),
    ]

    text = "\n".join(render_summary(snapshot, Path("/r.json")))

    assert (
        "cyclomatic_complexity: 3 functions, p50 2, p90 6, max 6; 1 unparsed [squadron-python-ast 1]"
        in text
    )
    assert "duplicated_lines: 15 in 2 file(s) [squadron-python-ast 1]" in text
    assert "coverable_lines: 40 in 1 file(s); 2 not in report [cobertura 7.17.0]" in text
    assert "covered_lines: 30 in 1 file(s); 2 not in report [cobertura 7.17.0]" in text
    assert "skipped by the tool's ignores" not in text
