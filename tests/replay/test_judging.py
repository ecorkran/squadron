"""Judging a replay set's pairs with a fake dispatcher: no model calls (slice 177 D5, D10)."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import (
    JudgeRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.judging import (
    JudgeCallError,
    JudgeInputError,
    JudgeJob,
    JudgeReply,
    contestants_of,
    judge_replay_set,
    plan_judging,
)
from tests.metrology.replay_builders import make_judge, make_replay

_PROJECT = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)
_T0 = datetime(2026, 11, 1, tzinfo=UTC)
_ORIGINAL = "# Original\nzzz-original"
_BOUND = 0.05

_DRAFT = re.compile(r"## Draft A\n\n(?P<a>.*?)\n\n## Draft B\n\n(?P<b>.*?)\n$", re.DOTALL)


def _usage(cost: float | None = 0.05) -> UsageRecord:
    return UsageRecord(
        model="m",
        alias="opus",
        profile="sdk",
        effort=None,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(prompt=120, completion=15),
        cost_usd=cost,
        cost_basis=CostBasis.PROVIDER,
    )


class _Judge:
    """Prefers the draft that sorts first; counts and records every prompt it is sent."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.fail_on_call: set[int] = set()
        self.hang_on_call: set[int] = set()
        self.reply_text: str | None = None  # overrides the verdict

    async def __call__(self, prompt: str) -> JudgeReply:
        self.prompts.append(prompt)
        call_number = len(self.prompts)
        if call_number in self.fail_on_call:
            raise JudgeCallError("provider said no")
        if call_number in self.hang_on_call:
            await asyncio.sleep(5)
        if self.reply_text is not None:
            return JudgeReply(self.reply_text, _usage())
        match = _DRAFT.search(prompt)
        assert match is not None, prompt
        winner = "A" if match["a"] <= match["b"] else "B"
        return JudgeReply(f"Because.\nWINNER: {winner}", _usage())


class _Store:
    def __init__(self) -> None:
        self.judgments: list[PairwiseJudgment] = []

    def write_judgment(self, judgment: PairwiseJudgment) -> str:
        self.judgments.append(judgment)
        return f"pair-{len(self.judgments)}"


def _replays(*drafts: str, **kw: object) -> list[tuple[str, ProducerReplay]]:
    return [
        (
            f"replay-{index}",
            make_replay(
                first_draft=draft,
                created_at=_T0 + timedelta(minutes=index),
                **kw,  # type: ignore[arg-type]
            ),
        )
        for index, draft in enumerate(drafts)
    ]


def _job(
    replays: list[tuple[str, ProducerReplay]],
    *,
    original: str | None = _ORIGINAL,
    existing: list[PairwiseJudgment] | None = None,
    judge: JudgeRef | None = None,
) -> JudgeJob:
    return JudgeJob(
        project_id=_PROJECT,
        phase=ReplayPhase.DESIGN,
        judge=judge or make_judge(),
        replays=replays,
        original_draft=original,
        existing=existing or [],
    )


async def _run(job: JudgeJob, judge: _Judge, store: _Store):  # pyright: ignore[reportUnknownParameterType]
    return await judge_replay_set(
        job, plan_judging(job), store=store, dispatcher=judge, timeout_s=_BOUND
    )


async def test_two_replays_and_the_original_make_three_pairs_and_six_calls() -> None:
    judge, store = _Judge(), _Store()
    job = _job(_replays("# A\naaa", "# B\nbbb"))

    summary = await _run(job, judge, store)

    assert (summary.judged, summary.failed, summary.calls) == (3, 0, 6)
    assert len(judge.prompts) == 6 and len(store.judgments) == 3
    pairs = {frozenset((j.a, j.b)) for j in store.judgments}
    assert len(pairs) == 3
    assert any(j.b.startswith("original:") for j in store.judgments)


async def test_the_second_call_of_each_pair_has_the_drafts_swapped() -> None:
    judge, store = _Judge(), _Store()

    await _run(_job(_replays("# A\naaa", "# B\nbbb"), original=None), judge, store)

    first, second = judge.prompts
    one, two = _DRAFT.search(first), _DRAFT.search(second)
    assert one is not None and two is not None
    assert (one["a"], one["b"]) == (two["b"], two["a"])


async def test_a_consistent_judge_gives_a_decisive_pair_outcome() -> None:
    judge, store = _Judge(), _Store()

    await _run(_job(_replays("# A\naaa", "# B\nbbb"), original=None), judge, store)

    (judgment,) = store.judgments
    assert judgment.outcome is PairOutcome.A  # "aaa" sorts first in both orders
    assert judgment.first_usage is not None and judgment.second_usage is not None


async def test_a_second_invocation_makes_no_calls() -> None:
    first_judge, store = _Judge(), _Store()
    replays = _replays("# A\naaa", "# B\nbbb")
    await _run(_job(replays), first_judge, store)

    job = _job(replays, existing=store.judgments)
    again = _Judge()
    summary = await _run(job, again, _Store())

    assert plan_judging(job).calls == 0
    assert again.prompts == [] and summary.calls == 0


async def test_adding_a_third_replay_judges_only_its_new_pairs() -> None:
    judge, store = _Judge(), _Store()
    two = _replays("# A\naaa", "# B\nbbb")
    await _run(_job(two), judge, store)
    three = [
        *two,
        ("replay-9", make_replay(first_draft="# C\nccc", created_at=_T0 + timedelta(hours=1))),
    ]

    job = _job(three, existing=store.judgments)
    plan = plan_judging(job)

    assert len(plan.pairs) == 3 and plan.calls == 6  # C against A, B and the original
    assert all("replay-9" in (x.ref, y.ref) for x, y in plan.pairs)


async def test_a_judgment_from_another_prompt_hash_does_not_count_as_judged() -> None:
    judge, store = _Judge(), _Store()
    replays = _replays("# A\naaa", "# B\nbbb")
    await _run(_job(replays, judge=make_judge("e" * 64)), judge, store)

    # `existing` is what the store returned for this judge, so another hash's are absent.
    assert plan_judging(_job(replays, existing=[])).calls == 6


def test_failed_replays_are_not_contestants_and_frontmatter_is_stripped() -> None:
    replays = [
        *_replays("---\ndocType: slice\n---\n# A\naaa"),
        ("replay-failed", make_replay(outcome=ReplayOutcome.FAILED, first_draft="# partial")),
        ("replay-empty", make_replay(first_draft=None)),
    ]

    contestants = contestants_of(_job(replays))

    assert [c.ref for c in contestants] == ["replay-0", "original:" + "a" * 40]
    assert contestants[0].draft == "# A\naaa"


async def test_the_dispatcher_receives_no_frontmatter() -> None:
    judge, store = _Judge(), _Store()
    replays = _replays("---\ndocType: slice\n---\n# A\naaa", "---\nstatus: draft\n---\n# B\nbbb")

    await _run(_job(replays, original=None), judge, store)

    assert all("docType" not in p and "status: draft" not in p for p in judge.prompts)
    assert all("Create a slice design." in p and "WINNER" in p for p in judge.prompts)


async def test_a_dispatch_that_raises_leaves_that_pair_unrecorded_and_the_rest_go_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    judge, store = _Judge(), _Store()
    judge.fail_on_call = {1}  # the first call of the first pair

    with caplog.at_level(logging.ERROR):
        summary = await _run(_job(_replays("# A\naaa", "# B\nbbb")), judge, store)

    assert (summary.judged, summary.failed) == (2, 1)
    assert len(store.judgments) == 2
    assert "provider said no" in caplog.text and "replay-0 vs replay-1" in caplog.text


async def test_a_call_that_outlives_the_bound_is_cancelled_and_counted_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    judge, store = _Judge(), _Store()
    judge.hang_on_call = {1}

    with caplog.at_level(logging.ERROR):
        summary = await _run(_job(_replays("# A\naaa", "# B\nbbb"), original=None), judge, store)

    assert (summary.judged, summary.failed) == (0, 1) and store.judgments == []
    assert "exceeded the 0.05s bound" in caplog.text and "replay-0 vs replay-1" in caplog.text


async def test_a_second_call_failure_after_the_first_returned_warns_with_its_spend(
    caplog: pytest.LogCaptureFixture,
) -> None:
    judge, store = _Judge(), _Store()
    judge.fail_on_call = {2}

    with caplog.at_level(logging.WARNING):
        summary = await _run(_job(_replays("# A\naaa", "# B\nbbb"), original=None), judge, store)

    assert (summary.judged, summary.failed, summary.calls) == (0, 1, 2)
    assert store.judgments == []  # not recorded: the next run repeats both calls
    warning = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert "120 prompt and 15 completion tokens" in warning and "$0.0500" in warning


async def test_a_reply_with_no_verdict_line_is_recorded_as_invalid() -> None:
    judge, store = _Judge(), _Store()
    judge.reply_text = "Both are fine, I cannot choose."

    summary = await _run(_job(_replays("# A\naaa", "# B\nbbb"), original=None), judge, store)

    (judgment,) = store.judgments
    assert judgment.outcome is PairOutcome.INVALID
    assert judgment.first_call.raw_tail == "Both are fine, I cannot choose."
    assert (summary.judged, summary.invalid) == (1, 1)


async def test_nothing_recorded_the_task_prompt_is_an_input_error() -> None:
    replays = [("replay-0", make_replay(task_prompt=None)), ("replay-1", make_replay(task_prompt=None))]

    with pytest.raises(JudgeInputError, match="task prompt"):
        await _run(_job(replays), _Judge(), _Store())


async def test_the_task_prompt_comes_from_the_earliest_replay_that_has_one() -> None:
    judge = _Judge()
    replays = [
        ("replay-1", make_replay(task_prompt=None, first_draft="# A\naaa", created_at=_T0)),
        (
            "replay-2",
            make_replay(
                task_prompt="THE TASK", first_draft="# B\nbbb", created_at=_T0 + timedelta(minutes=1)
            ),
        ),
    ]

    await _run(_job(replays, original=None), judge, _Store())

    assert all("THE TASK" in p for p in judge.prompts)
