"""Amoeba's two-step answering pipeline, end to end (slice 949 Success Criteria 1-4, 6).

Unit tests cover each rule; this file covers only what needs the executor: the files a
real run writes, a reply handed from one step to the next, and a resume that has to get
that reply back from persisted run state.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import squadron.cli.commands.run  # noqa: F401  # registers step and action types
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.state import StateManager
from squadron.providers.base import ProviderCapabilities
from squadron.providers.errors import ProviderError
from tests.pipeline.actions.dispatch_helpers import DISPATCH_MODULE as _P
from tests.pipeline.actions.dispatch_helpers import make_registry
from tests.pipeline.actions.dispatch_helpers import openrouter_profile as _openrouter_profile
from tests.pipeline.actions.test_dispatch_input import RecordingAgent

_EXTRACT_REPLY = 'Here are the claims: {"claims": ["c1", "c2"]}'
_CLAIMS_JSON = '{"claims": ["c1", "c2"]}'
_QUESTION = "What is claimed?\n"


class FailingAgent(RecordingAgent):
    """An agent whose model call fails, after recording the prompt it was sent."""

    async def handle_message(self, message):  # type: ignore[no-untyped-def,override]
        self.prompts.append(message.content)
        raise ProviderError("injected provider failure")
        yield  # pragma: no cover - makes this an async generator


def _pipeline() -> PipelineDefinition:
    extract = StepConfig(
        step_type="dispatch",
        name="extract",
        config={
            "prompt": "Extract the claims.",
            "prompt_files": ["question.md"],
            "allowed_tools": [],
            "reply_format": "json",
            "reply_file": "claims.json",
            "delivered_prompt_file": "extract.prompt.md",
        },
    )
    answer = StepConfig(
        step_type="dispatch",
        name="answer",
        config={
            "prompt": "Answer from the claims.",
            "reply_from": "extract",
            "allowed_tools": [],
            "reply_file": "answer.md",
            "delivered_prompt_file": "answer.prompt.md",
        },
    )
    return PipelineDefinition(name="amoeba", description="t", params={}, steps=[extract, answer])


def _resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = ("stub-model", "openrouter")
    resolver.resolve_full.return_value = ResolvedModel("stub-model", "openrouter")
    resolver.cascade_candidates.return_value = []
    return resolver


async def _run(
    tmp_path: Path,
    agents: list[RecordingAgent],
    sm: StateManager,
    run_id: str,
    *,
    start_from: str | None = None,
) -> PipelineResult:
    """Run the pipeline in *tmp_path*; each model call gets the next agent in *agents*."""
    registry = make_registry(MagicMock())
    spawned = iter(agents)

    async def spawn(_config: object) -> RecordingAgent:
        return next(spawned)

    registry.spawn = spawn
    # A provider that reads no files, so allowed_tools: [] is a real isolation guarantee.
    stub_provider = SimpleNamespace(capabilities=ProviderCapabilities(can_read_files=False))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_P}.get_provider", return_value=stub_provider),
    ):
        result = await execute_pipeline(
            _pipeline(),
            {},
            resolver=_resolver(),
            cf_client=MagicMock(),
            cwd=str(tmp_path),
            run_id=run_id,
            start_from=start_from,
            observer=sm.observer(run_id),
            runs_dir=tmp_path / "runs",
        )
    sm.finalize(run_id, result)
    return result


def _new_run(tmp_path: Path) -> tuple[StateManager, str]:
    (tmp_path / "question.md").write_text(_QUESTION)
    sm = StateManager(runs_dir=tmp_path / "runs")
    return sm, sm.init_run("amoeba", {})


@pytest.mark.asyncio
async def test_two_steps_pass_files_and_the_reply_with_nothing_else(tmp_path: Path) -> None:
    sm, run_id = _new_run(tmp_path)
    extract_agent, answer_agent = RecordingAgent(_EXTRACT_REPLY), RecordingAgent("the answer")

    result = await _run(tmp_path, [extract_agent, answer_agent], sm, run_id)

    assert result.status == ExecutionStatus.COMPLETED
    extract_prompt = (tmp_path / "extract.prompt.md").read_text()
    assert extract_prompt == f"Extract the claims.\n\n{_QUESTION}"
    assert extract_agent.prompts == [extract_prompt]
    assert (tmp_path / "claims.json").read_text() == _CLAIMS_JSON
    answer_prompt = (tmp_path / "answer.prompt.md").read_text()
    assert answer_prompt == f"Answer from the claims.\n\n{_CLAIMS_JSON}"
    assert "Extract the claims." not in answer_prompt
    assert (tmp_path / "answer.md").read_text() == "the answer"


@pytest.mark.asyncio
async def test_a_reply_with_no_json_fails_the_step_and_leaves_the_old_file(tmp_path: Path) -> None:
    sm, run_id = _new_run(tmp_path)
    (tmp_path / "claims.json").write_bytes(b'{"previous": true}')
    answer_agent = RecordingAgent("never asked")

    result = await _run(tmp_path, [RecordingAgent("no object here"), answer_agent], sm, run_id)

    assert result.status == ExecutionStatus.FAILED
    assert (tmp_path / "claims.json").read_bytes() == b'{"previous": true}'
    assert answer_agent.prompts == []


@pytest.mark.asyncio
async def test_resume_hands_the_restored_reply_to_the_next_step(tmp_path: Path) -> None:
    sm, run_id = _new_run(tmp_path)
    first = await _run(tmp_path, [RecordingAgent(_EXTRACT_REPLY), FailingAgent()], sm, run_id)
    assert first.status == ExecutionStatus.FAILED
    assert sm.first_unfinished_step(run_id, _pipeline()) == "answer"
    (tmp_path / "claims.json").write_text("changed on disk after the run")  # the reply comes from state
    resumed_agent = RecordingAgent("the answer")

    result = await _run(tmp_path, [resumed_agent], sm, run_id, start_from="answer")

    assert result.status == ExecutionStatus.COMPLETED
    assert resumed_agent.prompts == [f"Answer from the claims.\n\n{_CLAIMS_JSON}"]


@pytest.mark.asyncio
async def test_resume_past_a_failed_step_fails_the_reader_naming_it(tmp_path: Path) -> None:
    sm, run_id = _new_run(tmp_path)
    first = await _run(tmp_path, [RecordingAgent("no object here")], sm, run_id)
    assert first.status == ExecutionStatus.FAILED
    answer_agent = RecordingAgent("never asked")

    result = await _run(tmp_path, [answer_agent], sm, run_id, start_from="answer")

    assert result.status == ExecutionStatus.FAILED
    (answer_result,) = [step for step in result.step_results if step.step_name == "answer"]
    assert "extract" in (answer_result.action_results[-1].error or "")
    assert answer_agent.prompts == []
