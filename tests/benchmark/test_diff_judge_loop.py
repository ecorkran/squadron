"""The judge loop and the ``DiffJudgment`` it writes (slice 426, Task 30)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from squadron.benchmark.diff_judge import JudgeContext, JudgeSummary, judge_case, normalized_diffs
from squadron.benchmark.diff_judge_budget import JudgeCapReached
from squadron.benchmark.diff_normalize import EMPTY_DIFF_TEXT
from squadron.benchmark.diff_pairs import Pair, contestants_for, pairs_for
from squadron.metrology.replay_models import JudgePick, PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment
from squadron.replay.judging import JudgeCallError, JudgeReply
from tests.benchmark.diff_judge_support import CONFIG_ABSENCES, diff_text, grid, replay_input
from tests.benchmark.slice_case_support import judge_ref, usage
from tests.benchmark.slice_runner_support import slice_case

CASE = slice_case()
NOW = datetime(2026, 11, 15, tzinfo=UTC)
LIMIT = 400000


class Dispatcher:
    """Answers ``WINNER: A`` to every prompt, or raises for the prompts it is told to."""

    def __init__(self, fail_when: set[int] | None = None, hang: set[int] | None = None) -> None:
        self.prompts: list[str] = []
        self._fail = fail_when or set()
        self._hang = hang or set()

    async def __call__(self, prompt: str) -> JudgeReply:
        self.prompts.append(prompt)
        call = len(self.prompts)
        if call in self._hang:
            await asyncio.sleep(30)
        if call in self._fail:
            raise JudgeCallError("provider down")
        return JudgeReply(text="The first is better.\nWINNER: A", usage=usage(0.04))


class Sidecars:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self.files[digest] = data
        return digest


class Store:
    def __init__(self) -> None:
        self.judgments: list[DiffJudgment] = []

    def write_diff_judgment(self, judgment: DiffJudgment) -> str:
        self.judgments.append(judgment)
        return judgment.record_id


def _no_cap() -> None:
    return None


def _context(
    dispatcher: Dispatcher,
    sidecars: Sidecars,
    store: Store,
    timeout_s: float = 5.0,
    before_call: Callable[[], None] = _no_cap,
) -> JudgeContext:
    return JudgeContext(
        benchmark_id="bench-3f9c0a1b2c3d4e5f",
        judge=judge_ref(),
        dispatcher=dispatcher,
        timeout_s=timeout_s,
        sidecars=sidecars,
        store=store,
        limit=LIMIT,
        before_call=before_call,
        clock=lambda: NOW,
    )


def _run(
    pairs: list[Pair], dispatcher: Dispatcher, timeout_s: float = 5.0
) -> tuple[JudgeSummary, Store, Sidecars]:
    store, sidecars, summary = Store(), Sidecars(), JudgeSummary()
    asyncio.run(
        judge_case(
            CASE,
            pairs,
            _context(dispatcher, sidecars, store, timeout_s),
            summary,
            on_judgment=lambda pair, judgment: None,
        )
    )
    return summary, store, sidecars


def _pairs(aliases: dict[str, int], reference: bytes | None = None) -> list[Pair]:
    inputs = grid(CASE, aliases)
    return pairs_for(contestants_for(CASE, inputs, reference or diff_text("reference")))


def test_a_pair_writes_one_judgment_with_both_calls_and_the_sidecar_hashes() -> None:
    pairs = [p for p in _pairs({"opus": 1, "sol": 1}) if not p.versus_reference]
    dispatcher = Dispatcher()

    summary, store, sidecars = _run(pairs, dispatcher)

    (judgment,) = store.judgments
    assert (summary.judged, summary.failed, summary.calls) == (1, 0, 2)
    assert judgment.first_call is not None and judgment.second_call is not None
    assert judgment.first_call.pick is JudgePick.A
    assert judgment.second_call.pick is JudgePick.A
    assert judgment.outcome is PairOutcome.INCONSISTENT  # A first, then A in the swapped order
    assert judgment.a_diff in sidecars.files and judgment.b_diff in sidecars.files


def test_the_sidecar_holds_exactly_the_normalized_diff_the_prompt_contained() -> None:
    noisy = diff_text("code") + (
        b"diff --git a/DEVLOG.md b/DEVLOG.md\n--- a/DEVLOG.md\n+++ b/DEVLOG.md\n@@ -1 +1 @@\n-a\n+b\n"
    )
    inputs = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1)]
    inputs[0] = inputs[0]._replace(diff=noisy)
    pairs = [
        p
        for p in pairs_for(contestants_for(CASE, inputs, diff_text("reference")))
        if not p.versus_reference
    ]
    dispatcher = Dispatcher()

    _, store, sidecars = _run(pairs, dispatcher)

    (judgment,) = store.judgments
    assert judgment.a_diff is not None
    stored = sidecars.files[judgment.a_diff].decode()
    assert stored == normalized_diffs(pairs)[pairs[0].a.ref].text
    assert "DEVLOG" not in stored
    assert all(stored in prompt for prompt in dispatcher.prompts)


def test_a_failed_pair_is_unrecorded_counted_and_logged_and_later_pairs_still_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pairs = _pairs({"opus": 1, "sol": 1})  # one cross pair, then two reference pairs
    dispatcher = Dispatcher(fail_when={1})

    with caplog.at_level(logging.ERROR):
        summary, store, _ = _run(pairs, dispatcher)

    assert (summary.failed, summary.judged) == (1, 2)
    assert len(store.judgments) == 2
    assert (pairs[0].a.ref, pairs[0].b.ref) not in {(j.a, j.b) for j in store.judgments}
    assert any(r.levelno == logging.ERROR and "provider down" in r.getMessage() for r in caplog.records)
    assert any(
        r.levelno == logging.ERROR and "was not judged" in r.getMessage() for r in caplog.records
    )


def test_a_timed_out_pair_is_unrecorded_and_the_loop_goes_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pairs = _pairs({"opus": 1, "sol": 1})
    dispatcher = Dispatcher(hang={1})

    with caplog.at_level(logging.ERROR):
        summary, store, _ = _run(pairs, dispatcher, timeout_s=0.05)

    assert (summary.failed, summary.judged) == (1, 2)
    assert len(store.judgments) == 2
    assert any("exceeded" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


def test_a_forfeit_makes_no_dispatch() -> None:
    inputs = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1, outcome=CONFIG_ABSENCES[0])]
    pairs = [
        p for p in pairs_for(contestants_for(CASE, inputs, diff_text("r"))) if not p.versus_reference
    ]
    dispatcher = Dispatcher()

    summary, store, _ = _run(pairs, dispatcher)

    assert dispatcher.prompts == []
    assert (summary.forfeits, summary.calls) == (1, 0)
    (judgment,) = store.judgments
    assert judgment.forfeit and judgment.first_call is None and judgment.outcome is PairOutcome.A


def test_an_absent_diff_gives_none_for_its_hash() -> None:
    inputs = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1, outcome=CONFIG_ABSENCES[1])]
    pairs = [
        p for p in pairs_for(contestants_for(CASE, inputs, diff_text("r"))) if not p.versus_reference
    ]

    _, store, _ = _run(pairs, Dispatcher())

    (judgment,) = store.judgments
    assert judgment.a_diff is not None
    assert judgment.b_diff is None


def test_an_empty_normalized_diff_is_judged_with_the_placeholder_text() -> None:
    only_bookkeeping = (
        b"diff --git a/DEVLOG.md b/DEVLOG.md\n--- a/DEVLOG.md\n+++ b/DEVLOG.md\n@@ -1 +1 @@\n-a\n+b\n"
    )
    inputs = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1)]
    inputs[0] = inputs[0]._replace(diff=only_bookkeeping)
    pairs = [
        p for p in pairs_for(contestants_for(CASE, inputs, diff_text("r"))) if not p.versus_reference
    ]
    dispatcher = Dispatcher()

    summary, store, sidecars = _run(pairs, dispatcher)

    assert summary.judged == 1
    assert all(EMPTY_DIFF_TEXT in prompt for prompt in dispatcher.prompts)
    (judgment,) = store.judgments
    assert judgment.a_diff is not None
    assert sidecars.files[judgment.a_diff].decode() == EMPTY_DIFF_TEXT


def test_a_cap_raised_before_a_call_stops_the_run_and_keeps_earlier_records() -> None:
    pairs = _pairs({"opus": 1, "sol": 1})
    store, sidecars, summary = Store(), Sidecars(), JudgeSummary()
    calls = iter(range(100))

    def stop_after_two_calls() -> None:
        if next(calls) >= 2:
            raise JudgeCapReached(1.0, 1.0)

    with pytest.raises(JudgeCapReached):
        asyncio.run(
            judge_case(
                CASE,
                pairs,
                _context(Dispatcher(), sidecars, store, before_call=stop_after_two_calls),
                summary,
                on_judgment=lambda pair, judgment: None,
            )
        )

    assert summary.judged == 1 and len(store.judgments) == 1  # the first pair, both calls
    assert summary.calls == 2  # the refused third call is not counted
