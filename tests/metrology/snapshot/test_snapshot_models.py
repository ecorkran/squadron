"""Tests for the code-snapshot record models (slice 400, D1/D2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import (
    RULE_SET_SOURCE_TOOL_DEFAULTS,
    AbsenceReason,
    CodeSnapshot,
    Distribution,
    EnvironmentIdentity,
    FunctionOverLimit,
    LanguageSnapshot,
    LengthLimits,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

TOOL = ToolIdentity(name="ruff", version="0.15.0", counting="findings per file")
RULES = RuleSetIdentity(source="pyproject.toml[tool.ruff]", content_hash="a" * 64)
ENVIRONMENT = EnvironmentIdentity(
    lockfile_path="uv.lock", lockfile_sha256="b" * 64, interpreter_version="3.12.4"
)
DISTRIBUTION = Distribution(count=2, total=30, min=10, p50=10, p90=20, max=20)


def present(metric: SnapshotMetric, **overrides: Any) -> Measurement:
    values: dict[str, Any] = {
        "metric": metric,
        "language": SourceLanguage.PYTHON,
        "tool": TOOL,
        "rule_set": RULES,
        "environment": ENVIRONMENT,
    }
    values.update(overrides)
    return Measurement(**values)


def absent(metric: SnapshotMetric, language: SourceLanguage = SourceLanguage.PYTHON) -> Measurement:
    return Measurement(
        metric=metric,
        language=language,
        absent=AbsenceReason.NO_ADAPTER,
        absent_detail="no adapter registered",
    )


def language_snapshot(
    language: SourceLanguage = SourceLanguage.PYTHON,
    order: list[SnapshotMetric] | None = None,
) -> LanguageSnapshot:
    metrics = order if order is not None else list(SnapshotMetric)
    return LanguageSnapshot(
        language=language,
        file_count=2,
        adapter=None,
        measurements=[absent(metric, language) for metric in metrics],
    )


def code_snapshot(**overrides: Any) -> CodeSnapshot:
    values: dict[str, Any] = {
        "snapshot_id": "snapshot-abc-def",
        "project_id": ProjectId(value="github.com/manta/example", source=ProjectIdSource.REMOTE),
        "commit_sha": "c" * 40,
        "measured_at": datetime(2026, 10, 22, tzinfo=UTC),
        "squadron_version": "0.23.8",
        "limits": LengthLimits(max_file_lines=None, max_function_lines=None, limits_declared=False),
        "exclusions": ["b/**", "a/**"],
        "languages": [language_snapshot()],
    }
    values.update(overrides)
    return CodeSnapshot(**values)


class TestMeasurementIdentity:
    def test_present_measurements_with_full_identity_are_accepted(self) -> None:
        present(SnapshotMetric.FILE_LENGTH, rule_set=None, environment=None)
        present(SnapshotMetric.LINT_COUNT, environment=None)
        present(SnapshotMetric.TYPE_ERRORS)

    def test_present_measurement_requires_a_tool(self) -> None:
        with pytest.raises(ValidationError, match="requires a tool"):
            present(SnapshotMetric.FILE_LENGTH, tool=None)

    @pytest.mark.parametrize("metric", [SnapshotMetric.LINT_COUNT, SnapshotMetric.TYPE_ERRORS])
    def test_present_lint_or_type_requires_a_rule_set(self, metric: SnapshotMetric) -> None:
        with pytest.raises(ValidationError, match="requires a rule_set"):
            present(metric, rule_set=None)

    def test_present_type_errors_requires_an_environment(self) -> None:
        with pytest.raises(ValidationError, match="requires an environment"):
            present(SnapshotMetric.TYPE_ERRORS, environment=None)

    def test_tool_defaults_rule_set_with_no_hash_is_accepted(self) -> None:
        defaults = RuleSetIdentity(source=RULE_SET_SOURCE_TOOL_DEFAULTS, content_hash=None)

        measurement = present(SnapshotMetric.LINT_COUNT, rule_set=defaults, environment=None)

        assert measurement.rule_set is not None
        assert measurement.rule_set.content_hash is None

    def test_absent_measurement_requires_a_detail(self) -> None:
        with pytest.raises(ValidationError, match="requires absent_detail"):
            Measurement(
                metric=SnapshotMetric.TYPE_ERRORS,
                language=SourceLanguage.PYTHON,
                absent=AbsenceReason.TOOL_MISSING,
            )

    @pytest.mark.parametrize(
        "values",
        [
            {"per_file": {"a.py": 1}},
            {"distribution": DISTRIBUTION},
            {"limit": 300},
            {"unparsed_files": ["a.py"]},
            {"tool_ignored_files": ["a.py"]},
            {
                "over_limit": [
                    FunctionOverLimit(path="a.py", qualified_name="f", start_line=1, length=60)
                ]
            },
        ],
    )
    def test_absent_measurement_carries_no_values(self, values: dict[str, Any]) -> None:
        with pytest.raises(ValidationError, match="carries no values"):
            Measurement(
                metric=SnapshotMetric.FILE_LENGTH,
                language=SourceLanguage.PYTHON,
                absent=AbsenceReason.TOOL_FAILED,
                absent_detail="timed out",
                **values,
            )

    def test_present_measurement_must_not_carry_an_absence_detail(self) -> None:
        with pytest.raises(ValidationError, match="must not carry absent_detail"):
            present(SnapshotMetric.FILE_LENGTH, absent_detail="stray")


class TestLimits:
    def test_declared_flag_must_match_the_limits(self) -> None:
        with pytest.raises(ValidationError, match="limits_declared"):
            LengthLimits(max_file_lines=300, max_function_lines=None, limits_declared=False)
        with pytest.raises(ValidationError, match="limits_declared"):
            LengthLimits(max_file_lines=None, max_function_lines=None, limits_declared=True)

    def test_a_non_positive_limit_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LengthLimits(max_file_lines=0, max_function_lines=None, limits_declared=True)


class TestLanguageSnapshot:
    def test_missing_metric_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="missing metrics"):
            language_snapshot(order=[SnapshotMetric.FILE_LENGTH])

    def test_duplicate_metric_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate metric"):
            language_snapshot(order=[*SnapshotMetric, SnapshotMetric.FILE_LENGTH])

    def test_measurement_for_another_language_is_rejected(self) -> None:
        measurements = [absent(metric, SourceLanguage.SHELL) for metric in SnapshotMetric]
        with pytest.raises(ValidationError, match="does not match"):
            LanguageSnapshot(
                language=SourceLanguage.PYTHON,
                file_count=1,
                adapter=None,
                measurements=measurements,
            )


class TestSerialization:
    def test_insertion_order_does_not_change_the_json(self) -> None:
        first = code_snapshot(
            exclusions=["b/**", "a/**"],
            languages=[
                language_snapshot(SourceLanguage.PYTHON),
                language_snapshot(SourceLanguage.SHELL, order=list(reversed(SnapshotMetric))),
            ],
        )
        second = code_snapshot(
            exclusions=["a/**", "b/**", "a/**"],
            languages=[
                language_snapshot(SourceLanguage.SHELL),
                language_snapshot(SourceLanguage.PYTHON, order=list(reversed(SnapshotMetric))),
            ],
        )

        assert first.model_dump_json() == second.model_dump_json()
        assert first.exclusions == ["a/**", "b/**"]

    def test_measurement_collections_are_sorted(self) -> None:
        measurement = present(
            SnapshotMetric.FUNCTION_LENGTH,
            rule_set=None,
            environment=None,
            per_file={"z.py": 1, "a.py": 2},
            unparsed_files=["z.py", "a.py"],
            tool_ignored_files=["y.ts", "b.ts"],
            over_limit=[
                FunctionOverLimit(path="b.py", qualified_name="g", start_line=9, length=70),
                FunctionOverLimit(path="a.py", qualified_name="f", start_line=3, length=60),
            ],
        )

        assert list(measurement.per_file) == ["a.py", "z.py"]
        assert measurement.unparsed_files == ["a.py", "z.py"]
        assert measurement.tool_ignored_files == ["b.ts", "y.ts"]
        assert [row.path for row in measurement.over_limit] == ["a.py", "b.py"]

    def test_duplicate_language_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate language"):
            code_snapshot(languages=[language_snapshot(), language_snapshot()])

    def test_json_round_trip_is_lossless(self) -> None:
        snapshot = code_snapshot(
            limits=LengthLimits(max_file_lines=300, max_function_lines=50, limits_declared=True),
            languages=[
                LanguageSnapshot(
                    language=SourceLanguage.PYTHON,
                    file_count=2,
                    adapter="python",
                    measurements=[
                        present(
                            SnapshotMetric.FILE_LENGTH,
                            rule_set=None,
                            environment=None,
                            per_file={"a.py": 10, "b.py": 20},
                            distribution=DISTRIBUTION,
                            limit=300,
                        ),
                        absent(SnapshotMetric.FUNCTION_LENGTH),
                        present(SnapshotMetric.LINT_COUNT, environment=None, per_file={"a.py": 3}),
                        present(SnapshotMetric.TYPE_ERRORS),
                        absent(SnapshotMetric.CYCLOMATIC_COMPLEXITY),
                        absent(SnapshotMetric.DUPLICATED_LINES),
                        absent(SnapshotMetric.COVERED_LINES),
                        absent(SnapshotMetric.COVERABLE_LINES),
                    ],
                )
            ],
        )

        restored = CodeSnapshot.model_validate_json(snapshot.model_dump_json())

        assert restored == snapshot
        assert restored.model_dump_json() == snapshot.model_dump_json()
