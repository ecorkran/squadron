"""The sandbox stages of slice-case qualification (slice 426 D5, D6).

A sandbox at the fork, then one at the tip. Both are collected through the adapter and sorted
by 422's ``sort_tests``; the full suite runs ``repeats`` times at the tip; what remains of the
fork's tests after the superseded and excluded ones is the regression selection. Nothing here
writes a record: it returns what it decided, and a failure it cannot attribute to the slice
propagates for the caller to record as ``harness_error``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from squadron.benchmark.adapter import SuiteSelection
from squadron.benchmark.qualify_survivors import excluded_unchanged
from squadron.benchmark.slice_discovery import SliceCandidate
from squadron.benchmark.slice_qualify_types import (
    ReusedRecord,
    SliceQualifyDeps,
    SliceSandbox,
    StageOutcome,
)
from squadron.benchmark.slice_task import TaskText
from squadron.benchmark.test_first import run_selection
from squadron.benchmark.test_sets import TestSets, sort_tests
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    TestRejection,
)
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification

BUILT_BY = "sq benchmark slice-cases build"
SOURCE_REF = "slice:{index}@{after_sha}"
_SOURCE_REF = re.compile(r"^slice:(?P<index>\d+)@(?P<after>\w+)$")


def source_ref(index: int, landing_after_sha: str) -> str:
    """The case's provenance reference; not part of the case id."""
    return SOURCE_REF.format(index=index, after_sha=landing_after_sha)


def parse_source_ref(case: BenchmarkCase) -> tuple[int, str]:
    """The slice index and landing sha a slice case was built from; anything else raises."""
    match = _SOURCE_REF.match(case.provenance.source_ref)
    if match is None:
        raise ValueError(f"case {case.case_id} is not a slice case: {case.provenance.source_ref!r}")
    return int(match["index"]), match["after"]


def run_sandbox_stages(
    candidate: SliceCandidate,
    task: TaskText,
    deps: SliceQualifyDeps,
    stored_for: Callable[[str], SliceQualification | None],
) -> StageOutcome | ReusedRecord:
    """Build the fork sandbox, look for a stored result for its environment, else compare.

    ``stored_for(digest)`` returns a reusable record for the fork's environment digest, or
    ``None``; when it answers, nothing further is built or run.
    """
    landing = candidate.landing
    with deps.sandbox_factory(landing.fork_sha) as fork:
        kept = _keep(fork, deps)
        earlier = stored_for(fork.identity.identity_digest)
        if earlier is not None:
            return ReusedRecord(earlier, tuple(kept))
        with deps.sandbox_factory(landing.tip_sha) as tip:
            kept += _keep(tip, deps)
            return _compare(candidate, task, fork, tip, deps, tuple(kept))


def _keep(sandbox: SliceSandbox, deps: SliceQualifyDeps) -> list[Path]:
    """With ``keep``, leave the sandbox in place and report its tree."""
    if not deps.keep:
        return []
    sandbox.keep()
    return [sandbox.context().tree]


def _compare(
    candidate: SliceCandidate,
    task: TaskText,
    fork: SliceSandbox,
    tip: SliceSandbox,
    deps: SliceQualifyDeps,
    kept: tuple[Path, ...],
) -> StageOutcome:
    fork_ctx, tip_ctx = fork.context(), tip.context()
    sets = sort_tests(deps.adapter.collect(fork_ctx), deps.adapter.collect(tip_ctx))
    runs = [
        run_selection(deps.suite_runner, tip_ctx, SuiteSelection.all_tests())
        for _ in range(deps.repeats)
    ]
    excluded = excluded_unchanged(sets.unchanged, runs)
    outcome = StageOutcome(
        start_environment=fork.identity,
        reference_environment=tip.identity,
        excluded_with_reasons=excluded,
        kept_paths=kept,
    )
    selection = _regression_selection(sets, excluded)
    if not selection:
        return _rejected(outcome, sets, excluded)
    grader_commands = deps.adapter.grader_commands(fork_ctx.tree)
    case = BenchmarkCase.build(
        project_id=deps.project_id,
        kind=CaseKind.SLICE,
        start_sha=candidate.landing.fork_sha,
        reference_sha=candidate.landing.tip_sha,
        task_text=task.text,
        hidden_tests=(),  # nodes only at the tip are the slice's own tests, never hidden (D5)
        hidden_fixtures=(),
        superseded_tests=sets.superseded,
        excluded_tests=tuple(node_id for node_id, _ in excluded),
        grader_commands=grader_commands,
        provenance=CaseProvenance(
            source_ref=source_ref(candidate.slice_index, candidate.landing.after_sha),
            created_at=deps.clock(),
            built_by=BUILT_BY,
        ),
    )
    return replace(outcome, case=case, detail=_counts(selection, sets, excluded))


def _regression_selection(
    sets: TestSets, excluded: tuple[tuple[str, TestRejection], ...]
) -> tuple[str, ...]:
    """The fork's tests minus the superseded ones (``unchanged``) minus the excluded ones."""
    excluded_ids = {node_id for node_id, _ in excluded}
    return tuple(node_id for node_id in sets.unchanged if node_id not in excluded_ids)


def _counts(
    selection: tuple[str, ...], sets: TestSets, excluded: tuple[tuple[str, TestRejection], ...]
) -> str:
    """The numbers the build line prints: regression nodes, superseded, excluded."""
    return (
        f"{len(selection)} regression nodes, {len(sets.superseded)} superseded, "
        f"{len(excluded)} excluded"
    )


def _rejected(
    outcome: StageOutcome, sets: TestSets, excluded: tuple[tuple[str, TestRejection], ...]
) -> StageOutcome:
    return replace(
        outcome,
        rejection=SliceCandidateRejection.NO_REGRESSION_SIGNAL,
        detail=_counts((), sets, excluded),
    )
