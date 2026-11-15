"""judge_pair: both orders, bounded, a failed call leaves the pair unrecorded (slice 426 D12)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.replay.judging import JudgeCallError, JudgeReply, judge_pair

_LABEL = "a vs b"
_FIRST_COST = 0.0123


def _reply(text: str, cost: float | None = None) -> JudgeReply:
    usage = (
        None
        if cost is None
        else UsageRecord(
            model="m",
            alias="opus",
            profile="sdk",
            effort=None,
            turns=1,
            duration_seconds=1.0,
            usage=TokenUsage(prompt=10, completion=2),
            cost_usd=cost,
            cost_basis=CostBasis.PROVIDER,
        )
    )
    return JudgeReply(text=text, usage=usage)


class _Dispatcher:
    """Answers the nth call from a script; an Exception entry is raised, a float sleeps first."""

    def __init__(self, script: list[JudgeReply | Exception]) -> None:
        self._script = script
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> JudgeReply:
        self.prompts.append(prompt)
        step = self._script[len(self.prompts) - 1]
        if isinstance(step, Exception):
            raise step
        return step


class _Counter:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def test_both_calls_succeed_and_on_call_runs_twice() -> None:
    dispatcher = _Dispatcher([_reply("one"), _reply("two")])
    counter = _Counter()

    result = asyncio.run(judge_pair("AB", "BA", dispatcher, 1.0, _LABEL, counter))

    assert result is not None
    assert [reply.text for reply in result] == ["one", "two"]
    assert dispatcher.prompts == ["AB", "BA"]
    assert counter.calls == 2


def test_first_call_timeout_gives_none_logs_error_and_counts_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = _Dispatcher([TimeoutError(), _reply("never")])
    counter = _Counter()

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(judge_pair("AB", "BA", dispatcher, 1.0, _LABEL, counter))

    assert result is None
    assert counter.calls == 1
    assert dispatcher.prompts == ["AB"]
    assert any(
        r.levelno == logging.ERROR and _LABEL in r.getMessage() and "bound" in r.getMessage()
        for r in caplog.records
    )


def test_first_call_error_gives_none_and_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = _Dispatcher([JudgeCallError("provider down"), _reply("never")])
    counter = _Counter()

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(judge_pair("AB", "BA", dispatcher, 1.0, _LABEL, counter))

    assert result is None
    assert counter.calls == 1
    assert any(r.levelno == logging.ERROR and "provider down" in r.getMessage() for r in caplog.records)


def test_second_call_failure_gives_none_and_warns_with_the_first_calls_spend(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = _Dispatcher([_reply("one", cost=_FIRST_COST), JudgeCallError("second failed")])
    counter = _Counter()

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(judge_pair("AB", "BA", dispatcher, 1.0, _LABEL, counter))

    assert result is None
    assert counter.calls == 2
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(_LABEL in message and "$0.0123" in message for message in warnings)


def test_a_hung_dispatcher_is_cut_at_the_timeout(caplog: pytest.LogCaptureFixture) -> None:
    async def hung(prompt: str) -> JudgeReply:
        await asyncio.sleep(30)
        return _reply(prompt)

    counter = _Counter()
    timeout_s = 0.05

    async def run() -> tuple[JudgeReply, JudgeReply] | None:
        loop = asyncio.get_running_loop()
        started = loop.time()
        pair = await judge_pair("AB", "BA", hung, timeout_s, _LABEL, counter)
        assert loop.time() - started < 5 * timeout_s
        return pair

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(run())

    assert result is None
    assert counter.calls == 1
    assert any(r.levelno == logging.ERROR for r in caplog.records)
