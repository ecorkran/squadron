"""The producer config a replay records carries the alias's wire settings (slice 420 D6)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.cli.commands.replay_common import config_ref
from squadron.metrology.replay_models import ProducerConfigRef


def _aliases(**extra: object) -> dict[str, dict[str, object]]:
    return {"a": {"model": "m", "profile": "openrouter", **extra}}


def _config_ref(**extra: object) -> ProducerConfigRef:
    aliases = _aliases(**extra)
    with (
        patch("squadron.cli.commands.replay_common.get_all_aliases", return_value=aliases),
        patch("squadron.models.aliases.get_all_aliases", return_value=aliases),
    ):
        return config_ref("a")


def test_alias_with_tool_use_false_records_false() -> None:
    assert _config_ref(tool_use=False).tool_use is False


def test_alias_with_no_tool_use_records_true_because_absence_means_allow() -> None:
    assert _config_ref().tool_use is True


@pytest.mark.parametrize("budget", [4096, None])
def test_max_output_tokens_is_recorded_when_set_and_none_when_not(budget: int | None) -> None:
    extra = {} if budget is None else {"max_output_tokens": budget}

    assert _config_ref(**extra).max_output_tokens == budget


def test_a_config_recorded_before_these_fields_loads_with_none() -> None:
    ref = ProducerConfigRef.model_validate_json(
        '{"alias": "a", "model": "m", "profile": "sdk", "effort_sent": null}'
    )

    assert (ref.tool_use, ref.max_output_tokens) == (None, None)
