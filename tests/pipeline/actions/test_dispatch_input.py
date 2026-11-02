"""DispatchAction reads prompt files and earlier replies before any model call (slice 949 D2, D3)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import Message
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext, ActionResult, prior_output_key
from tests.pipeline.actions.dispatch_helpers import DISPATCH_MODULE as _P
from tests.pipeline.actions.dispatch_helpers import make_context, make_registry
from tests.pipeline.actions.dispatch_helpers import openrouter_profile as _openrouter_profile


class RecordingAgent:
    """A stub agent that records each prompt it is sent and answers with a fixed reply."""

    def __init__(self, reply: str = "model reply") -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        self.prompts.append(message.content)
        response = MagicMock(spec=Message)
        response.content = self.reply
        response.metadata = {}
        yield response


async def run_dispatch(ctx: ActionContext, agent: RecordingAgent) -> ActionResult:
    registry = make_registry(AsyncMock())
    registry.spawn = AsyncMock(return_value=agent)
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        return await DispatchAction().execute(ctx)


def context_in(tmp_path: Path, **params: object) -> ActionContext:
    return make_context(params=dict(params), cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_prompt_files_reach_the_model_in_order(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("AAA")
    (tmp_path / "b.md").write_text("BBB")
    agent = RecordingAgent()

    result = await run_dispatch(context_in(tmp_path, prompt="P", prompt_files=["a.md", "b.md"]), agent)

    assert result.success is True
    assert agent.prompts == ["P\n\nAAA\n\nBBB"]


@pytest.mark.asyncio
async def test_prompt_files_without_a_prompt_do_not_fall_back_to_other_sources(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("AAA")
    agent = RecordingAgent()

    result = await run_dispatch(context_in(tmp_path, prompt_files=["a.md"]), agent)

    assert result.success is True
    assert agent.prompts == ["AAA"]


@pytest.mark.asyncio
async def test_a_missing_prompt_file_fails_before_the_model_is_called(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    agent = RecordingAgent()

    with caplog.at_level(logging.WARNING, logger=_P):
        result = await run_dispatch(context_in(tmp_path, prompt="P", prompt_files=["gone.md"]), agent)

    assert result.success is False
    assert "gone.md" in (result.error or "")
    assert agent.prompts == []
    assert any(r.levelno == logging.WARNING and "gone.md" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_an_earlier_steps_reply_reaches_the_model_after_the_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("AAA")
    earlier = ActionResult(success=True, action_type="dispatch", outputs={"response": "EARLIER"})
    ctx = context_in(tmp_path, prompt="P", prompt_files=["a.md"], reply_from="extract")
    ctx.prior_outputs[prior_output_key("extract", "dispatch", 0)] = earlier
    agent = RecordingAgent()

    result = await run_dispatch(ctx, agent)

    assert result.success is True
    assert agent.prompts == ["P\n\nAAA\n\nEARLIER"]


@pytest.mark.asyncio
async def test_a_reply_from_a_step_with_no_result_fails_naming_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    agent = RecordingAgent()

    with caplog.at_level(logging.WARNING, logger=_P):
        result = await run_dispatch(context_in(tmp_path, prompt="P", reply_from="extract"), agent)

    assert result.success is False
    assert "extract" in (result.error or "")
    assert agent.prompts == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# --- the reply contract at the call site (slice 949 D4, D5) ---


@pytest.mark.asyncio
async def test_a_json_step_writes_its_files_and_records_reply_json(tmp_path: Path) -> None:
    agent = RecordingAgent(reply='Here: {"a": 1}')
    ctx = context_in(
        tmp_path,
        prompt="P",
        reply_format="json",
        reply_file="out/claims.json",
        delivered_prompt_file="out/prompt.md",
    )

    result = await run_dispatch(ctx, agent)

    assert result.success is True
    assert result.outputs["reply_json"] == '{"a": 1}'
    assert result.outputs["response"] == 'Here: {"a": 1}'
    assert (tmp_path / "out/claims.json").read_bytes() == b'{"a": 1}'
    assert (tmp_path / "out/prompt.md").read_bytes() == b"P"


@pytest.mark.asyncio
async def test_a_json_step_with_no_object_fails_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    agent = RecordingAgent(reply="prose only")
    ctx = context_in(tmp_path, prompt="P", reply_format="json", reply_file="claims.json")

    with caplog.at_level(logging.WARNING, logger=_P):
        result = await run_dispatch(ctx, agent)

    assert result.success is False
    assert result.error == "reply contains no JSON object"
    assert result.outputs["response"] == "prose only"
    assert not (tmp_path / "claims.json").exists()
    assert any("no JSON object" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_a_write_failure_fails_the_step_with_a_warning_naming_the_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "reply.txt").mkdir()  # a directory where the reply file should go
    agent = RecordingAgent(reply="ok")
    ctx = context_in(tmp_path, prompt="P", reply_file="reply.txt")

    with caplog.at_level(logging.WARNING, logger=_P):
        result = await run_dispatch(ctx, agent)

    assert result.success is False
    assert "reply.txt" in (result.error or "")
    assert any(r.levelno == logging.WARNING and "reply.txt" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "earlier",
    [
        ActionResult(success=False, action_type="dispatch", outputs={"response": "partial"}),
        ActionResult(success=True, action_type="dispatch", outputs={}),  # kept an artifact: no call
    ],
    ids=["failed", "no-response"],
)
async def test_a_reply_from_an_unusable_result_fails_the_reader_naming_the_step(
    tmp_path: Path, earlier: ActionResult
) -> None:
    ctx = context_in(tmp_path, prompt="P", reply_from="extract")
    ctx.prior_outputs[prior_output_key("extract", "dispatch", 0)] = earlier
    agent = RecordingAgent()

    result = await run_dispatch(ctx, agent)

    assert result.success is False
    assert "extract" in (result.error or "")
    assert agent.prompts == []
