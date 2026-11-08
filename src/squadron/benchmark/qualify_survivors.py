"""Stage 7: repeated reference runs and case construction (slice 422 D8, D9). Filled in by task 24."""

from __future__ import annotations

from squadron.benchmark.file_states import FileStates
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, QualifySandbox
from squadron.benchmark.test_sets import TestSets
from squadron.metrology.benchmark_models import HiddenTestVerdict


def qualify_survivors(
    sandbox: QualifySandbox,
    candidate: FixCandidate,
    task_text: str,
    sets: TestSets,
    verdicts: tuple[HiddenTestVerdict, ...],
    states: FileStates,
    deps: QualifyDeps,
) -> QualifyResult:
    """Run the full suite at the reference ``repeats`` times and build the case (task 24)."""
    raise NotImplementedError("stage 7 (repeats, exclusions, case construction) is task 24")
