"""Slice-case rows in the yield report (slice 426, Task 22)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.benchmark.slice_yield import (
    HEADING,
    build_slice_yield,
    render_slice_text,
    slice_rows_json,
)
from squadron.benchmark.yield_report import build_yield, render_json, render_text
from squadron.cli.app import app
from squadron.cli.commands import benchmark_common as common_module
from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.slice_case_support import PROJECT, environment, qualification
from tests.benchmark.test_yield_report import record as fix_record

Q, R, H = (
    QualificationOutcome.QUALIFIED,
    QualificationOutcome.REJECTED,
    QualificationOutcome.HARNESS_ERROR,
)
OTHER = ProjectId(value="github.com/manta/other", source=ProjectIdSource.REMOTE)


def _stored(
    index: int,
    outcome: QualificationOutcome,
    rejection: SliceCandidateRejection | None = None,
    *,
    project: ProjectId = PROJECT,
    age: int = 0,
) -> SliceQualification:
    base = qualification(
        outcome,
        index=index,
        rejection=rejection,
        start_environment=environment() if outcome is Q else None,
    )
    return base.model_copy(
        update={
            "project_id": project,
            "created_at": datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=age),
        }
    )


def _records() -> list[SliceQualification]:
    return [
        _stored(1, Q),
        _stored(2, Q),
        _stored(3, R, SliceCandidateRejection.NO_DESIGN_AT_FORK),
        _stored(4, R, SliceCandidateRejection.NO_DESIGN_AT_FORK),
        _stored(5, R, SliceCandidateRejection.MULTIPLE_LANDINGS),
        _stored(6, H),
        _stored(1, Q, project=OTHER),
    ]


def test_rows_count_qualified_each_rejection_value_and_harness_errors_per_project() -> None:
    rows = {row.project: row for row in build_slice_yield(_records())}

    mine = rows[PROJECT.value]
    assert (mine.candidates, mine.qualified, mine.harness_errors) == (6, 2, 1)
    assert mine.rejected == {
        SliceCandidateRejection.NO_DESIGN_AT_FORK: 2,
        SliceCandidateRejection.MULTIPLE_LANDINGS: 1,
    }
    assert rows[OTHER.value].qualified == 1


def test_the_latest_record_of_a_slice_is_the_one_counted() -> None:
    older = _stored(1, R, SliceCandidateRejection.NO_CODE_CHANGE, age=0)
    newer = _stored(1, Q, age=5)

    (row,) = build_slice_yield([newer, older])

    assert (row.candidates, row.qualified, row.rejected) == (1, 1, {})


def test_every_rejection_value_is_listed_when_nonzero() -> None:
    records = [
        _stored(index, R, rejection)
        for index, rejection in enumerate(SliceCandidateRejection, start=10)
    ]

    text = render_slice_text(build_slice_yield(records))

    for rejection in SliceCandidateRejection:
        assert f"{rejection.value} 1" in text
    assert text.splitlines()[0].startswith(HEADING)


def test_text_and_json_carry_the_rows_beside_the_fix_rows() -> None:
    report = build_yield(
        [fix_record("alpha", "a", Q, case_id="case-aaaaaaaaaaaaaaaa", env=environment())],
        [],
        3,
        0.1,
        slice_qualifications=_records(),
    )

    text = render_text(report)
    payload = json.loads(render_json(report))

    assert "project  " in text and HEADING in text
    assert text.index(HEADING) > text.index("separability")
    assert payload["slice_cases"] == slice_rows_json(build_slice_yield(_records()))
    assert payload["rows"]


def test_slice_rows_without_fix_rows_still_print() -> None:
    report = build_yield([], [], 3, 0.1, slice_qualifications=_records())

    assert render_text(report).startswith("no fix qualification records\n")
    assert HEADING in render_text(report)


def test_no_slice_records_leaves_the_output_unchanged() -> None:
    plain = build_yield(
        [fix_record("alpha", "a", Q, case_id="case-aaaaaaaaaaaaaaaa", env=environment())], [], 3, 0.1
    )
    with_empty = build_yield(
        [fix_record("alpha", "a", Q, case_id="case-aaaaaaaaaaaaaaaa", env=environment())],
        [],
        3,
        0.1,
        slice_qualifications=[],
    )

    assert render_text(plain) == render_text(with_empty)
    assert render_json(plain) == render_json(with_empty)
    assert "slice_cases" not in json.loads(render_json(plain))
    assert HEADING not in render_text(plain)


def test_the_yield_command_prints_stored_slice_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "store"
    monkeypatch.setattr(common_module, "resolve_store_dir", lambda cwd: directory)
    monkeypatch.chdir(tmp_path)
    store = SliceCaseRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=directory)))
    for stored in _records():
        store.write_slice_qualification(stored)

    text = CliRunner().invoke(app, ["benchmark", "yield"])
    as_json = CliRunner().invoke(app, ["benchmark", "yield", "--json"])

    assert text.exit_code == 0, text.output
    assert HEADING in text.output and "no_design_at_fork 2" in text.output
    assert {row["project"] for row in json.loads(as_json.output)["slice_cases"]} == {
        PROJECT.value,
        OTHER.value,
    }
