"""Console output for ``sq replay`` (slice 177).

Formats values the replay core produces; no logic about running a replay lives here.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from squadron.core.usage import format_usd
from squadron.metrology.replay_models import ProducerConfigRef, ProducerReplay
from squadron.replay.runner import ReplayPlan, ReplaySetSummary

DECLINED = "Not confirmed; nothing was run."


def _config_label(config: ProducerConfigRef) -> str:
    return f"{config.alias} ({config.model}, {config.profile or 'no profile'})"


def render_plan(plan: ReplayPlan, console: Console) -> None:
    configs = ", ".join(_config_label(config) for config in plan.configs)
    bound = (
        f"{plan.llm_call_bound} LLM calls at most "
        f"({len(plan.configs)} configs x 2 x (1 + {plan.max_revisions}))"
    )
    lines = [
        f"Replay {plan.phase.value} for slice {plan.slice_index} ({plan.slice_name})",
        f"  start commit   {plan.start_sha}",
        f"  reviewer       {plan.reviewer.alias} ({plan.reviewer.model})",
        f"  max revisions  {plan.max_revisions}",
        f"  configs        {configs}",
        f"  upper bound    {bound}",
    ]
    for line in lines:
        console.print(Text(line))


def render_record(record: ProducerReplay, console: Console) -> None:
    """One line per finished config."""
    rounds = "-" if record.rounds is None else str(record.rounds)
    cost = "no cost" if record.cost_usd is None else format_usd(record.cost_usd)
    failure = "" if record.failure_class is None else f" [{record.failure_class}]"
    priced, actions = record.priced
    console.print(
        Text(
            f"{record.config.alias}: {record.outcome.value}{failure}  rounds {rounds}  "
            f"{cost} ({priced} of {actions} priced)  {record.wall_seconds:.0f}s"
        )
    )


def render_skipped(alias: str, reason: str, console: Console) -> None:
    console.print(Text(f"{alias}: skipped - {reason}"))


def render_summary(summary: ReplaySetSummary, console: Console) -> None:
    line = f"{len(summary.records)} replay record(s) written"
    if summary.skipped:
        line += f", {len(summary.skipped)} config(s) skipped"
    console.print(Text(line))
    if summary.stopped is not None:
        console.print(Text(f"Stopped: {summary.stopped}"))


def render_judge_plan(
    pairs: int, calls: int, judge_alias: str, prompt_hash: str, console: Console
) -> None:
    judge = f"{judge_alias} (prompt {prompt_hash[:6]})"
    console.print(Text(f"{pairs} pair(s) to judge: {calls} judge calls with {judge}"))


def render_judge_summary(judged: int, failed: int, invalid: int, console: Console) -> None:
    line = f"{judged} pair(s) judged"
    if invalid:
        line += f", {invalid} with no verdict"
    if failed:
        line += f", {failed} failed"
    console.print(Text(line))
