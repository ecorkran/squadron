"""Judging the pairs of one slice case: the size rule and the judge loop (slice 426 D12, D14, D15).

The judge sees normalized diffs only. Before any call the longest pair prompt is measured
against ``benchmark.judge_max_prompt_chars``: past it the whole case is excluded, never
truncated. Then each pair is forfeited without a call or judged in both orders through 177's
``judge_pair``; a pair whose calls fail is logged at ERROR, left unrecorded and counted, so a
rerun retries it. The dispatcher, the sidecars and the store are injected.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from squadron.benchmark.diff_normalize import NormalizedDiff, normalize
from squadron.benchmark.diff_pairs import Pair, forfeit_for, forfeit_judgment
from squadron.benchmark.diff_prompt import diff_prompt
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.replay_models import JudgeRef
from squadron.metrology.slice_case_models import DiffJudgment
from squadron.replay.judge import combine, parse_verdict
from squadron.replay.judging import JudgeDispatcher, judge_pair

_logger = logging.getLogger(__name__)


class DiffSidecarWriter(Protocol):
    def put(self, data: bytes) -> str: ...


class DiffJudgmentWriter(Protocol):
    def write_diff_judgment(self, judgment: DiffJudgment) -> str: ...


@dataclass(frozen=True)
class OverSize:
    """The longest pair prompt of a case that is over the limit, and who produced it."""

    longest_chars: int
    contestant: str  # the ref of the contestant with the longer diff in that pair


def normalized_diffs(pairs: Iterable[Pair]) -> dict[str, NormalizedDiff]:
    """Each present contestant's normalized diff, by ref."""
    found: dict[str, NormalizedDiff] = {}
    for pair in pairs:
        for contestant in (pair.a, pair.b):
            if contestant.diff is not None and contestant.ref not in found:
                found[contestant.ref] = normalize(contestant.diff)
    return found


def check_size(
    case: BenchmarkCase, pairs: Sequence[Pair], limit: int, normalized: Mapping[str, NormalizedDiff]
) -> OverSize | None:
    """``OverSize`` when the longest pair prompt exceeds ``limit`` characters, else ``None``.

    Both orders of a pair have the same length, so one prompt per pair is measured. A pair
    with an absent side has no prompt and is skipped. Nothing is ever shortened.
    """
    longest: OverSize | None = None
    for pair in pairs:
        if forfeit_for(pair) is not None:
            continue
        text_a, text_b = normalized[pair.a.ref].text, normalized[pair.b.ref].text
        length = len(diff_prompt(case.task_text, text_a, text_b))
        if length > limit and (longest is None or length > longest.longest_chars):
            longest = OverSize(length, pair.a.ref if len(text_a) >= len(text_b) else pair.b.ref)
    return longest


@dataclass
class JudgeSummary:
    """What a judge run did, summed over cases."""

    judged: int = 0
    forfeits: int = 0
    failed: int = 0
    calls: int = 0


@dataclass(frozen=True)
class JudgeContext:
    """Everything the loop is handed besides the case and its pairs."""

    benchmark_id: str
    judge: JudgeRef
    dispatcher: JudgeDispatcher
    timeout_s: float
    sidecars: DiffSidecarWriter
    store: DiffJudgmentWriter
    limit: int
    #: Runs before each judge call and raises to stop the run (the run cap); forfeits make
    #: no call, so they never reach it.
    before_call: Callable[[], None]
    clock: Callable[[], datetime]


async def judge_case(
    case: BenchmarkCase,
    pairs: Sequence[Pair],
    context: JudgeContext,
    summary: JudgeSummary,
    *,
    on_judgment: Callable[[Pair, DiffJudgment], None],
) -> None:
    """Record every pair of the case.

    ``context.before_call`` may raise to stop the run; the records written so far stay, and a
    pair stopped between its two calls is left unrecorded.
    """
    normalized = normalized_diffs(pairs)
    hashes = {ref: context.sidecars.put(diff.text.encode("utf-8")) for ref, diff in normalized.items()}
    for pair in pairs:
        outcome = forfeit_for(pair)
        if outcome is not None:
            judgment = forfeit_judgment(
                benchmark_id=context.benchmark_id,
                case_id=case.case_id,
                pair=pair,
                outcome=outcome,
                diff_hashes=hashes,
                judge=context.judge,
                max_prompt_chars=context.limit,
                created_at=context.clock(),
            )
            context.store.write_diff_judgment(judgment)
            summary.forfeits += 1
            on_judgment(pair, judgment)
            continue
        judgment = await _judge_pair(case, pair, normalized, hashes, context, summary)
        if judgment is None:
            summary.failed += 1
            continue
        context.store.write_diff_judgment(judgment)
        summary.judged += 1
        on_judgment(pair, judgment)


async def _judge_pair(
    case: BenchmarkCase,
    pair: Pair,
    normalized: Mapping[str, NormalizedDiff],
    hashes: Mapping[str, str],
    context: JudgeContext,
    summary: JudgeSummary,
) -> DiffJudgment | None:
    text_a, text_b = normalized[pair.a.ref].text, normalized[pair.b.ref].text
    replies = await judge_pair(
        diff_prompt(case.task_text, text_a, text_b),
        diff_prompt(case.task_text, text_b, text_a),
        context.dispatcher,
        context.timeout_s,
        f"{case.case_id} {pair.a.ref} vs {pair.b.ref}",
        on_call=lambda: _before_call(context, summary),
    )
    if replies is None:
        _logger.error("pair %s vs %s of %s was not judged", pair.a.ref, pair.b.ref, case.case_id)
        return None
    first, second = replies
    one, two = parse_verdict(first.text), parse_verdict(second.text)
    return DiffJudgment(
        benchmark_id=context.benchmark_id,
        case_id=case.case_id,
        judge=context.judge,
        a=pair.a.ref,
        b=pair.b.ref,
        a_diff=hashes.get(pair.a.ref),
        b_diff=hashes.get(pair.b.ref),
        forfeit=False,
        first_call=one,
        second_call=two,
        outcome=combine(one.pick, two.pick),
        first_usage=first.usage,
        second_usage=second.usage,
        max_prompt_chars=context.limit,
        created_at=context.clock(),
    )


def _before_call(context: JudgeContext, summary: JudgeSummary) -> None:
    """The cap check, then the count: a call the cap refuses is not a call made."""
    context.before_call()
    summary.calls += 1
