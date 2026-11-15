"""Building slice cases from recorded landings, with doubles (slice 426, Task 20)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.slice_case_build import (
    NOT_ATTEMPTED,
    SliceBuildDeps,
    SliceBuildResult,
    build_slice_cases,
)
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    QualificationOutcome,
)
from squadron.metrology.project_id import ProjectId
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.metrology.slice_range_models import SliceLanding, SliceRanges
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.slice_case_support import PROJECT
from tests.benchmark.slice_qualify_support import Setup, typical_setup
from tests.benchmark.slice_repos import landing_of, two_parent_landing


class _Ranges:
    def __init__(self, slices: dict[int, list[SliceLanding]]) -> None:
        self._ranges = SliceRanges(record_id="sliceranges-t", project_id=PROJECT, slices=slices)

    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
        return self._ranges


def _deps(setup: Setup, indices: dict[int, list[SliceLanding]]) -> SliceBuildDeps:
    return SliceBuildDeps(qualify=setup.deps, ranges=_Ranges(indices), case_sets=setup.cases)


def _build(setup: Setup, indices: dict[int, list[SliceLanding]]) -> SliceBuildResult:
    return build_slice_cases(setup.deps.repo, "slices", _deps(setup, indices), lambda line: None)


def _three(tmp_path: Path) -> tuple[Setup, dict[int, list[SliceLanding]]]:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)
    landing = landing_of(built)
    second = landing.model_copy(update={"after_sha": "e" * 40})
    # 501 has its design, task file and plan at the fork; 599 has none; 598 landed twice.
    return setup, {598: [landing, second], 599: [landing], built.index: [landing]}


def test_one_line_per_index_in_the_record(tmp_path: Path) -> None:
    setup, indices = _three(tmp_path)

    result = _build(setup, indices)

    assert [line.split()[1] for line in result.lines] == ["501", "598", "599"]
    assert result.lines[0].startswith("slice 501 qualified case-")
    assert "(2 regression nodes, 2 superseded, 2 excluded)" in result.lines[0]
    assert result.lines[1].startswith(
        f"slice 598 {SliceCandidateRejection.MULTIPLE_LANDINGS.value}: 2 landings"
    )
    assert result.lines[2].startswith(f"slice 599 {SliceCandidateRejection.NO_DESIGN_AT_FORK.value}:")
    assert result.stopped_at is None


def test_every_index_has_a_stored_result(tmp_path: Path) -> None:
    setup, indices = _three(tmp_path)

    _build(setup, indices)

    stored = {q.slice_index: q for q in setup.qualifications.list_slice_qualifications(PROJECT)}
    assert set(stored) == {501, 598, 599}
    assert stored[598].rejection is SliceCandidateRejection.MULTIPLE_LANDINGS


def test_a_second_build_reuses_unchanged_candidates(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    first = typical_setup(tmp_path / "s", built)
    _build(first, {built.index: [landing_of(built)]})
    second = typical_setup(tmp_path / "s", built)

    result = _build(second, {built.index: [landing_of(built)]})

    assert result.lines[0].startswith("slice 501 qualified case-")
    assert second.adapter.collected == []
    assert second.suite.calls == 0


def test_a_harness_error_candidate_runs_again_on_the_next_build(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    failing = typical_setup(
        tmp_path / "s",
        built,
        fail=lambda sha: SandboxError("no space") if sha == built.landing.tip else None,
    )
    indices = {built.index: [landing_of(built)]}
    first = _build(failing, indices)
    retry = typical_setup(tmp_path / "s", built)

    second = _build(retry, indices)

    assert first.lines[0].startswith("slice 501 harness_error:")
    assert second.lines[0].startswith("slice 501 qualified case-")
    assert retry.suite.calls > 0


def test_the_case_set_holds_exactly_the_qualified_ids_and_keeps_earlier_members(
    tmp_path: Path,
) -> None:
    setup, indices = _three(tmp_path)
    earlier = BenchmarkCase.build(
        project_id=PROJECT,
        kind=CaseKind.SLICE,
        start_sha="1" * 40,
        reference_sha="2" * 40,
        task_text="another",
        hidden_tests=(),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(),
        provenance=CaseProvenance(
            source_ref="slice:7@abc", created_at=datetime(2026, 1, 1, tzinfo=UTC), built_by="t"
        ),
    )
    setup.cases.write_case(earlier)
    setup.cases.write_case_set("slices", [earlier.case_id])

    result = _build(setup, indices)

    qualified = [
        q.case_id
        for q in setup.qualifications.list_slice_qualifications(PROJECT)
        if q.outcome is QualificationOutcome.QUALIFIED
    ]
    assert result.case_set is not None
    assert set(result.case_set.case_ids) == {earlier.case_id, *qualified}
    assert len(qualified) == 1
    assert result.case_set.version == 2


def test_no_qualified_case_and_no_earlier_set_writes_no_set(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)

    result = _build(setup, {599: [landing_of(built)]})

    assert result.case_set is None
    assert setup.cases.get_case_set("slices") is None


def test_a_harness_error_stops_the_build_and_later_indexes_are_not_attempted(
    tmp_path: Path,
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(
        tmp_path / "s",
        built,
        fail=lambda sha: SandboxError("no space") if sha == built.landing.tip else None,
    )
    landing = landing_of(built)
    indices = {500: [landing], built.index: [landing], 502: [landing]}

    result = _build(setup, indices)

    assert result.stopped_at == built.index
    assert result.lines[0].startswith("slice 500 no_design_at_fork:")
    assert result.lines[1].startswith("slice 501 harness_error:")
    assert result.lines[2] == NOT_ATTEMPTED.format(index=502, stopped=built.index)
    stored = {q.slice_index: q for q in setup.qualifications.list_slice_qualifications(PROJECT)}
    assert set(stored) == {500, 501}
    assert stored[501].outcome is QualificationOutcome.HARNESS_ERROR


def test_no_slice_ranges_record_halts_naming_the_command(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)

    class _Nothing:
        def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
            return None

    deps = SliceBuildDeps(qualify=setup.deps, ranges=_Nothing(), case_sets=setup.cases)
    with pytest.raises(BuildHalted, match="sq metrology slice-ranges"):
        build_slice_cases(setup.deps.repo, "slices", deps, lambda line: None)
