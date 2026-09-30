"""The alias's effort reaches the AgentConfig each pipeline path builds (slice 931 D11).

Each path runs its real builder and is stopped where its config reaches a provider, as the
shared ``agent_config_sites`` capture does. The review path is covered with the review
client (it builds its own config there).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import Effort
from squadron.pipeline.resolver import ResolvedModel
from tests.providers.agent_config_sites import capture_config


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", [Effort.low, None])
async def test_dispatch_puts_effort_on_its_config(tmp_path: Path, effort: Effort | None) -> None:
    from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry

    config = await capture_config(
        lambda: one_shot_dispatch_with_telemetry(
            prompt="p", model_id="m", profile_name="sdk", cwd=str(tmp_path), effort=effort
        )
    )

    assert config.effort is effort


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", [Effort.none, None])
async def test_summary_one_shot_puts_effort_on_its_config(effort: Effort | None) -> None:
    from squadron.pipeline.summary_oneshot import capture_summary_via_profile

    config = await capture_config(
        lambda: capture_summary_via_profile(
            instructions="summarize", model_id=None, profile="sdk", effort=effort
        )
    )

    assert config.effort is effort


@pytest.mark.asyncio
async def test_summary_action_passes_the_resolved_effort(tmp_path: Path) -> None:
    from squadron.pipeline.actions import summary as summary_action
    from squadron.pipeline.models import ActionContext

    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel("m", "openrouter", effort=Effort.high)
    capture = AsyncMock(return_value=("text", {}))
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={},
        step_name="summary",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(tmp_path),
    )

    with patch.object(summary_action, "capture_summary_via_profile_with_telemetry", capture):
        await summary_action._execute_summary(  # pyright: ignore[reportPrivateUsage]
            context=context,
            instructions="summarize",
            summary_model_alias="glm-high",
            emit_destinations=[],
            action_type="summary",
        )

    assert capture.await_args is not None
    assert capture.await_args.kwargs["effort"] is Effort.high


def test_summary_run_cli_passes_effort(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from squadron.cli.app import app

    capture = AsyncMock(return_value="summary text")
    with patch("squadron.cli.commands.summary_run.capture_summary_via_profile", capture):
        result = CliRunner().invoke(
            app,
            [
                "_summary-run",
                "--template",
                "minimal",
                "--profile",
                "openrouter",
                "--model",
                "m",
                "--effort",
                "low",
            ],
        )

    assert result.exit_code == 0, result.output
    assert capture.await_args is not None
    assert capture.await_args.kwargs["effort"] is Effort.low
