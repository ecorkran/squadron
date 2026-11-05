"""The replay judge sends its alias's effort and records it (slice 420 D3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import Effort
from squadron.metrology.replay_models import JudgeRef
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.usage_capture import EFFORT_SENT_KEY
from squadron.providers.base import TURNS_KEY
from squadron.replay.judge_dispatch import judge_effort_sent, one_shot_judge_dispatcher
from squadron.replay.judging import JudgeCallError
from tests.providers.agent_config_sites import capture_config

_MOD = "squadron.replay.judge_dispatch"


def _resolver(profile: str | None, effort: Effort | None) -> MagicMock:
    resolver = MagicMock()
    resolver.return_value.resolve_full.return_value = ResolvedModel(
        "judge-model", profile, effort=effort, alias="judge"
    )
    return resolver


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", [Effort.low, None])
async def test_judge_call_puts_the_alias_effort_on_its_config(effort: Effort | None) -> None:
    with patch(f"{_MOD}.ModelResolver", _resolver("sdk", effort)):
        dispatch = one_shot_judge_dispatcher("judge")
        config = await capture_config(lambda: dispatch("compare these"))

    assert config.effort is effort


@pytest.mark.asyncio
@pytest.mark.parametrize("sent", [Effort.low, None])
async def test_judge_reply_usage_records_the_effort_sent(sent: Effort | None) -> None:
    async def _call(**kwargs: object) -> tuple[str, dict[str, object]]:
        usage_metadata = kwargs["usage_metadata"]
        assert isinstance(usage_metadata, dict)
        usage_metadata[EFFORT_SENT_KEY] = sent
        usage_metadata[TURNS_KEY] = 1  # a record is built only when the call reported something
        return "verdict", {}

    with (
        patch(f"{_MOD}.ModelResolver", _resolver("sdk", Effort.low)),
        patch(f"{_MOD}.one_shot_dispatch_with_telemetry", AsyncMock(side_effect=_call)),
    ):
        reply = await one_shot_judge_dispatcher("judge")("compare these")

    assert reply.usage is not None
    assert reply.usage.effort == (None if sent is None else sent.value)


def test_judge_effort_sent_follows_the_profile_gate() -> None:
    with patch(f"{_MOD}.ModelResolver", _resolver("sdk", Effort.high)):
        assert judge_effort_sent("judge") is Effort.high
    with patch(f"{_MOD}.ModelResolver", _resolver("sdk", None)):
        assert judge_effort_sent("judge") is None


def test_profile_less_alias_cannot_be_a_judge() -> None:
    with patch(f"{_MOD}.ModelResolver", _resolver(None, Effort.high)):
        with pytest.raises(JudgeCallError, match="no profile"):
            judge_effort_sent("judge")
        with pytest.raises(JudgeCallError, match="no profile"):
            one_shot_judge_dispatcher("judge")


def test_judge_ref_recorded_before_effort_was_tracked_loads_as_none() -> None:
    ref = JudgeRef.model_validate_json('{"alias": "j", "model": "m", "prompt_hash": "h"}')

    assert ref.effort_sent is None
