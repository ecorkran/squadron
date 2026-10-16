"""Group a slice's stored replays into judge jobs, one per replay set (slice 177 D5)."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Protocol

from squadron.metrology.project_id import ProjectId
from squadron.metrology.replay_models import (
    JudgeRef,
    PairwiseJudgment,
    ProducerReplay,
    ReplayPhase,
)
from squadron.replay.judging import (
    JudgeDispatcher,
    JudgeJob,
    JudgeSummary,
    JudgmentStore,
    judge_replay_set,
    plan_judging,
)
from squadron.replay.start_point import StartPoint

_logger = logging.getLogger(__name__)


class ReplayStoreReader(Protocol):
    def list_replays(
        self, project_id: str, phase: ReplayPhase | None = None, replay_set: str | None = None
    ) -> list[tuple[str, ProducerReplay]]: ...

    def list_judgments(
        self, project_id: str, phase: ReplayPhase | None = None, judge: JudgeRef | None = None
    ) -> list[PairwiseJudgment]: ...


def build_jobs(
    store: ReplayStoreReader,
    project_id: ProjectId,
    phase: ReplayPhase,
    slice_index: int,
    judge: JudgeRef,
    original: Callable[[], StartPoint],
) -> list[JudgeJob]:
    """One job per replay set of this slice, with this judge's existing judgments.

    ``original`` reads the original artifact's start point; it is called only when there
    are replays to judge. An original that no longer matches a set's recorded
    ``original_sha`` is left out of that set, with a WARNING.
    """
    by_set: dict[str, list[tuple[str, ProducerReplay]]] = defaultdict(list)
    for record_id, replay in store.list_replays(project_id.value, phase):
        if replay.slice_index == slice_index:
            by_set[replay.replay_set].append((record_id, replay))
    if not by_set:
        return []
    start = original()
    judged = store.list_judgments(project_id.value, phase, judge)
    return [
        JudgeJob(
            project_id=project_id,
            phase=phase,
            judge=judge,
            replays=replays,
            original_draft=_original_draft(start, replays),
            existing=[j for j in judged if j.replay_set == replay_set],
        )
        for replay_set, replays in by_set.items()
    ]


def _original_draft(start: StartPoint, replays: Sequence[tuple[str, ProducerReplay]]) -> str | None:
    recorded = replays[0][1].original_sha
    if start.original_sha != recorded:
        _logger.warning(
            "the original artifact is now at %s but these replays recorded %s; "
            "the original is left out of this set",
            start.original_sha,
            recorded,
        )
        return None
    return start.original_first_draft


def total_calls(jobs: Sequence[JudgeJob]) -> tuple[int, int]:
    """``(pairs, judge calls)`` still to make across ``jobs``."""
    plans = [plan_judging(job) for job in jobs]
    return sum(len(plan.pairs) for plan in plans), sum(plan.calls for plan in plans)


async def judge_jobs(
    jobs: Sequence[JudgeJob],
    *,
    store: JudgmentStore,
    dispatcher: JudgeDispatcher,
    timeout_s: float,
) -> JudgeSummary:
    """Judge every job's unjudged pairs; the summary adds up across jobs."""
    total = JudgeSummary()
    for job in jobs:
        part = await judge_replay_set(
            job, plan_judging(job), store=store, dispatcher=dispatcher, timeout_s=timeout_s
        )
        total.judged += part.judged
        total.failed += part.failed
        total.invalid += part.invalid
        total.calls += part.calls
    return total
