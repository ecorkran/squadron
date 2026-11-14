"""What ``sq benchmark run`` prints (slice 424 Task 33): per-replay lines, summary, warnings."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence

from squadron.benchmark.bench_plan import PlannedReplay
from squadron.benchmark.bench_refusals import AUTH_CHECK_COMMAND
from squadron.benchmark.run_services import KeptSandbox
from squadron.metrology.benchmark_replay_enums import ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun, CaseDrop, ImplementationReplay

NO_COST = "unpriced"
NO_LEAK_VERDICT = "-"
KEEP_WARNING = (
    "warning: the kept home holds copies of your auth files; delete the kept sandbox when done"
)


def _cost(cost_usd: float | None) -> str:
    return NO_COST if cost_usd is None else f"${cost_usd:.4f}"


def replay_line(planned: PlannedReplay, result: ImplementationReplay | CaseDrop) -> str:
    """One line per replay: record id, outcome, leak verdict, cost; or the case drop."""
    if isinstance(result, CaseDrop):
        reason = str(result.reason)  # a StrEnum or free text
        return f"{planned.record_id}  dropped case {result.case_id}: {reason}"
    leak = NO_LEAK_VERDICT if result.leak is None else result.leak.verdict.value
    return f"{planned.record_id}  {result.outcome.value}  leak {leak}  {_cost(result.cost_usd)}"


class ReplayReporter:
    """Prints each replay as it finishes, and the auth-check reminder at each profile's first
    ``no_run_state`` replay."""

    def __init__(self, echo: Callable[[str], None]) -> None:
        self._echo = echo
        self._profiles_reminded: set[str | None] = set()

    def __call__(self, planned: PlannedReplay, result: ImplementationReplay | CaseDrop) -> None:
        self._echo(replay_line(planned, result))
        if (
            isinstance(result, ImplementationReplay)
            and result.outcome is ProducerOutcome.NO_RUN_STATE
            and planned.config.profile not in self._profiles_reminded
        ):
            self._profiles_reminded.add(planned.config.profile)
            self._echo(
                f"  note: {planned.config.profile} produced no run state; "
                f"run `{AUTH_CHECK_COMMAND}` to check its login in the scrubbed environment"
            )


def _counts(title: str, values: Iterable[str]) -> str:
    counted = Counter(values)
    body = ", ".join(f"{name} {count}" for name, count in sorted(counted.items())) or "none"
    return f"{title}: {body}"


def summary_lines(run: BenchmarkRun, replays: Iterable[ImplementationReplay]) -> list[str]:
    """The benchmark's summary over every stored replay (earlier invocations included)."""
    stored = list(replays)
    lines = [
        f"benchmark {run.benchmark_id}: {run.status.value}",
        _counts("outcomes", (r.outcome.value for r in stored)),
        _counts("absence", (r.absence.value for r in stored if r.absence is not None)),
        _counts("leak", (r.leak.verdict.value for r in stored if r.leak is not None)),
        f"spent: ${run.spent_usd:.4f} of run cap ${run.run_cap_usd:.2f}  "
        f"({run.unpriced_replays} replays reported no cost)",
    ]
    for drop in run.case_drops:
        reason = str(drop.reason)
        lines.append(f"dropped case {drop.case_id}: {reason}")
    return lines


def kept_lines(kept: Sequence[KeptSandbox]) -> list[str]:
    """The kept sandbox paths and the warning that the home holds copies of your login files."""
    lines = [
        line
        for sandbox in kept
        for line in (
            f"tree: {sandbox.tree}",
            f"home: {sandbox.home}",
            f"out: {sandbox.output_dir}",
        )
    ]
    return [*lines, KEEP_WARNING]
