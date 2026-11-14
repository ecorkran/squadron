"""Load test for the in-dispatch cost cap on the SDK path (slice 424, D9).

Required by ``.claude/rules/python.md``'s load-test tier: the SDK budget is a budget path,
and the stop it triggers runs on the event loop that streams the dispatch. The unit tests in
``tests/pipeline/test_sdk_budget.py`` assert the mapping from the SDK's result to
``cost_cap``; this one streams many messages whose cumulative cost crosses a capped
session's budget and asserts two bounds a single-call unit test cannot see: the overshoot
stays within one dispatch's cost, and the stop path does not block the event loop (a counter
coroutine beside the stream ticks at least once per streamed message). The fake client takes
its cap from the options the session was opened with, so a dropped budget lets the stream run
to its end and fails the test.

No wall-clock thresholds: the loop-liveness bound is a count, not a duration.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from squadron.pipeline.control_params import RUN_MAX_COST
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.sdk_session import SDK_BUDGET_SUBTYPE, open_pipeline_session
from squadron.providers.base import USAGE_KEY
from tests.pipeline.conftest import ScriptedClient, sdk_text

RUN_CAP_USD = 1.0
MESSAGE_COST_USD = 0.01  # what each streamed message adds; one dispatch's worth of overshoot
STREAMED_MESSAGES = 400  # far more than the budget allows, so the stop is what ends the stream
MODEL_ID = "claude-haiku-4-5-20251001"


class _BudgetedClient(ScriptedClient):
    """Streams text messages, charging each, and stops with the SDK's budget result.

    Like the real SDK, it takes its budget from the options it was constructed with, so the
    stop happens only if the code under test put the cap there. No budget, no stop.
    """

    def __init__(self, options: ClaudeAgentOptions) -> None:
        super().__init__()
        self._budget_usd = options.max_budget_usd
        self.messages_streamed = 0
        self.total_cost_usd = 0.0

    def receive_response(self) -> Any:  # type: ignore[override]
        return self._stream()

    async def _stream(self) -> Any:
        for _ in range(STREAMED_MESSAGES):
            await asyncio.sleep(0)  # a message arrives from the CLI; the loop gets a turn
            self.messages_streamed += 1
            self.total_cost_usd += MESSAGE_COST_USD
            yield sdk_text("working")
            if self._budget_usd is not None and self.total_cost_usd >= self._budget_usd:
                yield ResultMessage(
                    subtype=SDK_BUDGET_SUBTYPE,
                    duration_ms=1,
                    duration_api_ms=1,
                    is_error=True,
                    num_turns=1,
                    session_id="sess-1",
                    result="budget reached",
                    total_cost_usd=self.total_cost_usd,
                )
                return


async def _count_ticks(ticks: list[int], stop: asyncio.Event) -> None:
    """Increment, then yield to the loop, until told to stop."""
    while not stop.is_set():
        ticks[0] += 1
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_a_capped_dispatch_stops_within_one_message_of_the_cap_without_blocking_the_loop(
    tmp_path: Path,
) -> None:
    clients: list[_BudgetedClient] = []

    def build_client(*, options: ClaudeAgentOptions) -> _BudgetedClient:
        clients.append(_BudgetedClient(options))
        return clients[-1]

    # The session is opened the way a run opens it, with the run's cap.
    with patch("squadron.pipeline.sdk_session.ClaudeSDKClient", side_effect=build_client):
        session = await open_pipeline_session(max_budget_usd=RUN_CAP_USD)
    client = clients[0]
    resolver = MagicMock()
    resolver.resolve.return_value = (MODEL_ID, None)
    resolver.resolve_full.return_value = ResolvedModel(MODEL_ID, None)
    definition = PipelineDefinition(
        name="cap",
        description="load",
        params={},
        steps=[
            StepConfig(step_type="dispatch", name="work", config={"prompt": "go", "model": MODEL_ID})
        ],
    )
    ticks = [0]
    stop = asyncio.Event()
    counter = asyncio.create_task(_count_ticks(ticks, stop))

    result = await execute_pipeline(
        definition,
        {RUN_MAX_COST: RUN_CAP_USD},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(tmp_path),
        sdk_session=session,
    )
    stop.set()
    await counter
    await session.disconnect()

    assert result.status is ExecutionStatus.FAILED
    failed = result.step_results[0].action_results[-1]
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    # The stream ended at the cap, not at the end of the script.
    assert client.messages_streamed < STREAMED_MESSAGES
    spent = failed.metadata[USAGE_KEY]["cost_usd"]  # type: ignore[index]
    assert RUN_CAP_USD <= spent <= RUN_CAP_USD + MESSAGE_COST_USD + 1e-9
    # The loop stayed live through the whole stream and the stop.
    assert ticks[0] >= client.messages_streamed
