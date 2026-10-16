"""Judge the pairs of one replay set (slice 177 D5).

Contestants are the set's replays that produced a first draft, plus the ``original``
artifact. Each unjudged pair is compared twice with the drafts swapped; a pair is recorded
only when both calls return. The model call is an injected dispatcher, so the tests make
no model calls.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from squadron.core.usage import UsageRecord
from squadron.metrology.project_id import ProjectId
from squadron.metrology.replay_models import (
    ORIGINAL_CONTESTANT_PREFIX,
    JudgeCall,
    JudgeRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.judge import combine, judge_prompt, parse_verdict, strip_frontmatter

_logger = logging.getLogger(__name__)


class JudgeCallError(Exception):
    """A judge dispatch failed; the dispatcher wraps whatever its provider raised."""


class JudgeInputError(Exception):
    """The set cannot be judged: nothing recorded what the producers were asked to do."""


@dataclass(frozen=True)
class JudgeReply:
    text: str
    usage: UsageRecord | None


#: Sends one judge prompt and returns the reply; raises ``JudgeCallError`` on failure.
JudgeDispatcher = Callable[[str], Awaitable[JudgeReply]]


class JudgmentStore(Protocol):
    def write_judgment(self, judgment: PairwiseJudgment) -> str: ...


@dataclass(frozen=True)
class Contestant:
    ref: str  # a replay record id, or ORIGINAL_CONTESTANT_PREFIX + sha
    draft: str  # frontmatter stripped


@dataclass(frozen=True)
class JudgePlan:
    """The pairs still to judge, and the calls they will cost, for confirmation."""

    pairs: tuple[tuple[Contestant, Contestant], ...]

    @property
    def calls(self) -> int:
        return 2 * len(self.pairs)


@dataclass
class JudgeSummary:
    judged: int = 0
    failed: int = 0
    invalid: int = 0  # recorded pairs whose outcome is INVALID
    calls: int = 0


@dataclass(frozen=True)
class JudgeJob:
    """One replay set to judge, with everything the judge reads."""

    project_id: ProjectId
    phase: ReplayPhase
    judge: JudgeRef
    replays: Sequence[tuple[str, ProducerReplay]]  # (record id, replay), one replay_set
    original_draft: str | None  # the original artifact's first draft, if it could be read
    existing: Sequence[PairwiseJudgment]  # judgments already made by this judge


def contestants_of(job: JudgeJob) -> list[Contestant]:
    """Replays that produced a first draft, oldest first, then the original."""
    found = [
        Contestant(record_id, strip_frontmatter(replay.first_draft))
        for record_id, replay in sorted(job.replays, key=lambda item: item[1].created_at)
        if replay.outcome is not ReplayOutcome.FAILED and replay.first_draft
    ]
    if job.original_draft and job.replays:
        sha = job.replays[0][1].original_sha
        found.append(
            Contestant(ORIGINAL_CONTESTANT_PREFIX + sha, strip_frontmatter(job.original_draft))
        )
    return found


def plan_judging(job: JudgeJob) -> JudgePlan:
    """The pairs this judge has not judged yet."""
    done = {frozenset((j.a, j.b)) for j in job.existing if j.replay_set == _replay_set(job)}
    pairs = tuple(
        pair
        for pair in itertools.combinations(contestants_of(job), 2)
        if frozenset((pair[0].ref, pair[1].ref)) not in done
    )
    return JudgePlan(pairs)


def _replay_set(job: JudgeJob) -> str:
    return job.replays[0][1].replay_set


def _task_prompt(job: JudgeJob) -> str:
    """What the producers were asked to do, from the earliest replay that recorded it."""
    for _, replay in sorted(job.replays, key=lambda item: item[1].created_at):
        if replay.task_prompt:
            return replay.task_prompt
    raise JudgeInputError(
        "no replay in the set recorded the task prompt, so there is nothing to judge against"
    )


def _prompt(task: str, draft_a: str, draft_b: str) -> str:
    return (
        f"{judge_prompt().strip()}\n\n## Task\n\n{task.strip()}\n\n"
        f"## Draft A\n\n{draft_a.strip()}\n\n## Draft B\n\n{draft_b.strip()}\n"
    )


async def judge_replay_set(
    job: JudgeJob,
    plan: JudgePlan,
    *,
    store: JudgmentStore,
    dispatcher: JudgeDispatcher,
    timeout_s: float,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> JudgeSummary:
    """Judge every pair in ``plan``; a failed pair is logged, not recorded, and the rest go on."""
    summary = JudgeSummary()
    if not plan.pairs:
        return summary
    task = _task_prompt(job)
    for first, second in plan.pairs:
        label = f"{first.ref} vs {second.ref}"
        calls = await _judge_pair(first, second, task, dispatcher, timeout_s, label, summary)
        if calls is None:
            summary.failed += 1
            continue
        judgment = _judgment(job, first, second, calls, now())
        store.write_judgment(judgment)
        summary.judged += 1
        summary.invalid += judgment.outcome is PairOutcome.INVALID
    return summary


async def _call(
    prompt: str, dispatcher: JudgeDispatcher, timeout_s: float, label: str, summary: JudgeSummary
) -> JudgeReply | None:
    """One bounded judge call; ``None`` after logging when it raised or timed out."""
    summary.calls += 1
    try:
        return await asyncio.wait_for(dispatcher(prompt), timeout=timeout_s)
    except TimeoutError:
        _logger.error("judge call for %s exceeded the %gs bound", label, timeout_s)
    except JudgeCallError as exc:
        _logger.error("judge call for %s failed: %s", label, exc)
    return None


async def _judge_pair(
    first: Contestant,
    second: Contestant,
    task: str,
    dispatcher: JudgeDispatcher,
    timeout_s: float,
    label: str,
    summary: JudgeSummary,
) -> tuple[JudgeReply, JudgeReply] | None:
    one = await _call(_prompt(task, first.draft, second.draft), dispatcher, timeout_s, label, summary)
    if one is None:
        return None
    two = await _call(_prompt(task, second.draft, first.draft), dispatcher, timeout_s, label, summary)
    if two is None:
        _logger.warning("pair %s left unjudged after its first call returned; %s", label, _spent(one))
        return None
    return one, two


def _spent(reply: JudgeReply) -> str:
    usage = reply.usage
    if usage is None:
        return "the first call's spend was not recorded"
    cost = "no cost recorded" if usage.cost_usd is None else f"${usage.cost_usd:.4f}"
    tokens = f"{usage.usage.prompt} prompt and {usage.usage.completion} completion tokens"
    return f"the first call spent {tokens}, {cost}"


def _judgment(
    job: JudgeJob,
    first: Contestant,
    second: Contestant,
    calls: tuple[JudgeReply, JudgeReply],
    created_at: datetime,
) -> PairwiseJudgment:
    one: JudgeCall = parse_verdict(calls[0].text)
    two: JudgeCall = parse_verdict(calls[1].text)
    return PairwiseJudgment(
        replay_set=_replay_set(job),
        project_id=job.project_id,
        phase=job.phase,
        judge=job.judge,
        a=first.ref,
        b=second.ref,
        first_call=one,
        second_call=two,
        outcome=combine(one.pick, two.pick),
        first_usage=calls[0].usage,
        second_usage=calls[1].usage,
        created_at=created_at,
    )
