"""Builders for the diff judge's tests (slice 426, Tasks 27-35)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence

from squadron.benchmark.diff_pairs import ReplayInput
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import DiffRef
from tests.benchmark.report_support import config
from tests.benchmark.test_grade_plan import make_replay

#: What each config absence looks like on a replay record.
CONFIG_ABSENCES = (
    ProducerOutcome.NO_COMMIT,
    ProducerOutcome.BLOCKED,
    ProducerOutcome.COST_CAP,
    ProducerOutcome.PRODUCER_FAILED,
)
HARNESS_ABSENCES = (
    ProducerOutcome.ENVIRONMENT_FAILED,
    ProducerOutcome.NO_RUN_STATE,
    ProducerOutcome.FROZEN_TEXT_MISMATCH,
)


def diff_text(label: str) -> bytes:
    """A small unified diff naming ``label``."""
    return (
        f"diff --git a/src/{label}.py b/src/{label}.py\n--- a/src/{label}.py\n"
        f"+++ b/src/{label}.py\n@@ -1 +1 @@\n-old\n+new {label}\n"
    ).encode()


def replay_input(
    case: BenchmarkCase,
    alias: str,
    sample: int,
    *,
    outcome: ProducerOutcome = ProducerOutcome.COMMITTED,
) -> ReplayInput:
    """One replay of ``case``: committed (with a diff) or absent as ``outcome`` says."""
    absence: AbsenceClass | None
    if outcome is ProducerOutcome.COMMITTED:
        absence = None
    elif outcome in CONFIG_ABSENCES:
        absence = AbsenceClass.CONFIG
    else:
        absence = AbsenceClass.HARNESS
    committed = outcome is ProducerOutcome.COMMITTED
    content = diff_text(f"{alias}{sample}") if committed else None
    record_id, replay = make_replay(
        case,
        sample,
        config=config(alias),
        outcome=outcome,
        absence=absence,
        diff=None if content is None else diff_ref(content),
        commit_sha="c" * 40 if committed else None,
    )
    return ReplayInput(f"{record_id}-{alias}", replay, content)


def diff_ref(content: bytes) -> DiffRef:
    return DiffRef(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content), files_changed=1)


def diff_reader(inputs: Sequence[ReplayInput]) -> Callable[[DiffRef], bytes]:
    """A ``diff_of`` over the inputs' diff bytes, by their sha256."""
    by_sha = {diff_ref(item.diff).sha256: item.diff for item in inputs if item.diff is not None}
    return lambda ref: by_sha[ref.sha256]


def grid(case: BenchmarkCase, aliases: Mapping[str, int]) -> list[ReplayInput]:
    """Committed replays: ``{alias: k}`` gives samples 1..k for each alias."""
    return [replay_input(case, alias, s) for alias, k in aliases.items() for s in range(1, k + 1)]
