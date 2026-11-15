"""The state one grade accumulates as its steps run (slice 425 D1).

``GradeRun`` is the one mutable thing in a grade: the sandbox, the adapters and readers the
steps share, and what the steps have learned so far. Steps take it and raise ``GradeAbsent``
when they cannot continue; ``grade_one`` reads it back to build the record.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from squadron.benchmark.adapter import NodeResult
from squadron.benchmark.grade_deps import GradeDeps, GradeSandbox, GradeTarget
from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.benchmark.replay_outcome import STDERR_TAIL_CHARS
from squadron.benchmark.tree_reader import PROCESS_FAILURES, TreeReader
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import ReviewSummary, SnapshotRef, SuppressionCounts
from squadron.metrology.grade_records import ReferenceGrade


class GitFailure(Exception):
    """A git command could not finish or exited non-zero; ``detail`` has its stderr tail."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass
class GradeRun:
    case: BenchmarkCase
    target: GradeTarget
    deps: GradeDeps
    sandbox: GradeSandbox
    adapter: GradingAdapter
    start: TreeReader
    reference: TreeReader
    #: The commit holding the subject's diff on top of the start commit.
    head_sha: str | None = None
    #: ``[tool.*]`` tables and files restored from the start commit, counted not graded (D4).
    config_edits: tuple[str, ...] = ()
    reinstalled: bool = False
    #: The sha256 of the producer's lock file; ``None`` when its tree has none.
    lockfile_sha256: str | None = None
    #: The case's reference grade (replays only) and its start tree's node ids.
    baseline: ReferenceGrade | None = None
    start_ids: tuple[str, ...] = ()
    #: What a reference records at the start tree, before its diff applies (D8).
    baseline_nodes_sha: str | None = None
    baseline_snapshot: SnapshotRef | None = None
    baseline_lint_total: int | None = None
    baseline_type_total: int | None = None
    review_floor: FloorStat | None = None
    producer_new_passed: int = 0
    producer_new_failed: int = 0
    snapshot: SnapshotRef | None = None
    lint_total: int | None = None
    type_total: int | None = None
    #: Existing test files the producer edited or deleted, cut to ``MAX_LISTED_ITEMS``.
    test_edits: tuple[str, ...] = ()
    test_edit_count: int = 0
    regression_selected: int = 0
    regression_failures: tuple[str, ...] = ()
    regression_failure_count: int = 0
    hidden_total: int = 0
    hidden_passed: int = 0
    hidden_failures: tuple[NodeResult, ...] = ()
    hidden_id_map_sha256: str | None = None
    injection_clashes: tuple[str, ...] = ()
    injection_clash_count: int = 0
    suppressions: SuppressionCounts = field(default_factory=SuppressionCounts)
    #: One summary per review run, in order; costs are as reported (``None`` when unreported).
    review_summaries: list[ReviewSummary] = field(default_factory=list[ReviewSummary])
    review_costs: list[float | None] = field(default_factory=list[float | None])

    def grading_cost_usd(self) -> float | None:
        """The sum of the priced review costs, ``None`` when none was priced."""
        priced = [cost for cost in self.review_costs if cost is not None]
        return sum(priced) if priced else None


def run_git(
    run: GradeRun, args: list[str], *, cwd: str, in_sandbox: bool, stdin: str | None = None
) -> str:
    """Run ``git`` and return stdout; a failure raises ``GitFailure`` with the stderr tail.

    In the sandbox git runs under the sandbox's own scrubbed environment (which carries the
    benchmark commit identity); in the user's checkout it runs under the caller's.
    """
    deps = run.deps
    try:
        if in_sandbox:
            result = deps.process_runner.run(
                ["git", *args],
                cwd=cwd,
                timeout=deps.git_timeout_s,
                env=run.sandbox.process_env(),
                stdin=stdin,
                replace_env=True,
            )
        else:
            result = deps.process_runner.run(
                ["git", *args], cwd=cwd, timeout=deps.git_timeout_s, stdin=stdin
            )
    except PROCESS_FAILURES as exc:
        raise GitFailure(f"git {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        tail = result.stderr.strip()[-STDERR_TAIL_CHARS:]
        raise GitFailure(f"git {' '.join(args)} exited {result.returncode}: {tail}")
    return result.stdout
