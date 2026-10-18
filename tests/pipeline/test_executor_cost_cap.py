"""The executor stops a run at the action that crosses pipeline.max_cost_usd (slice 947 D4/D5)."""

from __future__ import annotations

import logging
from itertools import count
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import set_config
from squadron.core.usage import TokenUsage, UsageRecord
from squadron.integrations.context_forge import SliceEntry
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps import register_step_type
from squadron.providers.base import USAGE_KEY

_step_names = count()


def _usage(cost_usd: float | None) -> dict[str, object]:
    return UsageRecord(
        model=None,
        alias="opus",
        profile=None,
        effort=None,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(),
        cost_usd=cost_usd,
        cost_basis=None,
    ).to_dict()


def _priced_action(cost_usd: float | None) -> MagicMock:
    """An action that succeeds and stamps ``cost_usd`` as its usage."""

    async def execute(ctx: object) -> ActionResult:
        return ActionResult(
            success=True, action_type="dispatch", outputs={}, metadata={USAGE_KEY: _usage(cost_usd)}
        )

    action = MagicMock()
    action.execute = AsyncMock(side_effect=execute)
    return action


def _step_type(name: str) -> str:
    """Register a step type that expands to one dispatch action; return its name."""
    step = MagicMock()
    step.expand.return_value = [("dispatch", {})]
    register_step_type(name, step)
    return name


def _flat_pipeline(step_count: int) -> PipelineDefinition:
    kind = _step_type(f"_cap_flat_{next(_step_names)}")
    return PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[StepConfig(step_type=kind, name=f"step-{i}", config={}) for i in range(step_count)],
    )


def _set_cap(tmp_path: Path, raw: str) -> None:
    set_config(COST_CAP_KEY, raw, project=True, cwd=str(tmp_path))


async def _run(
    definition: PipelineDefinition, action: MagicMock, tmp_path: Path, **kwargs: object
) -> PipelineResult:
    return await execute_pipeline(
        definition,
        {},
        resolver=kwargs.pop("resolver", MagicMock()),  # type: ignore[arg-type]
        cf_client=kwargs.pop("cf_client", MagicMock()),  # type: ignore[arg-type]
        cwd=str(tmp_path),
        _action_registry={"dispatch": action},
    )


@pytest.mark.asyncio
async def test_no_cap_configured_runs_to_completion(
    patch_config_paths: dict[str, Path], tmp_path: Path
) -> None:
    action = _priced_action(500.0)

    result = await _run(_flat_pipeline(3), action, tmp_path)

    assert result.status is ExecutionStatus.COMPLETED
    assert action.execute.await_count == 3


@pytest.mark.asyncio
async def test_the_action_that_crosses_the_cap_fails_and_nothing_runs_after_it(
    patch_config_paths: dict[str, Path], tmp_path: Path
) -> None:
    _set_cap(tmp_path, "1.0")
    action = _priced_action(0.6)

    result = await _run(_flat_pipeline(3), action, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert action.execute.await_count == 2  # the third step never ran
    failed = result.step_results[-1].action_results[0]
    assert failed.success is False
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    assert failed.error == (
        f"run spent $1.20 this invocation, over {COST_CAP_KEY} $1.00; "
        "raise the cap and resume to continue"
    )


@pytest.mark.asyncio
async def test_an_invalid_cap_fails_the_run_at_start_before_any_step(
    patch_config_paths: dict[str, Path], tmp_path: Path
) -> None:
    _set_cap(tmp_path, "0")
    action = _priced_action(0.1)

    with pytest.raises(ValueError, match=COST_CAP_KEY):
        await _run(_flat_pipeline(2), action, tmp_path)

    action.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpriced_actions_do_not_count_and_warn_once(
    patch_config_paths: dict[str, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _set_cap(tmp_path, "0.01")
    action = _priced_action(None)

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.run_spend"):
        result = await _run(_flat_pipeline(3), action, tmp_path)

    assert result.status is ExecutionStatus.COMPLETED
    assert [r.getMessage() for r in caplog.records if "reported no cost" in r.getMessage()] == [
        "step step-0 (alias opus) reported no cost; the run's spend is a lower bound"
    ]


@pytest.mark.asyncio
async def test_fan_out_branches_share_one_tally(
    patch_config_paths: dict[str, Path], tmp_path: Path
) -> None:
    _set_cap(tmp_path, "1.0")
    inner = _step_type(f"_cap_inner_{next(_step_names)}")
    definition = PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="fan_out",
                name="fan",
                config={"models": ["a", "b", "c"], "inner": {inner: {}}},
            )
        ],
    )
    resolver = MagicMock()
    resolver.resolve.side_effect = lambda model: (model, None)
    action = _priced_action(0.4)

    result = await _run(definition, action, tmp_path, resolver=resolver)

    assert action.execute.await_count == 3  # concurrent branches all ran
    assert result.status is ExecutionStatus.FAILED
    # The step's error names the real total ($1.20), not one branch's share.
    assert result.step_results[0].error == (
        f"run spent $1.20 this invocation, over {COST_CAP_KEY} $1.00; "
        "raise the cap and resume to continue"
    )


@pytest.mark.parametrize("policy", ["stop", "continue"])
@pytest.mark.asyncio
async def test_each_items_share_one_tally_and_the_cap_stops_the_batch_under_either_policy(
    patch_config_paths: dict[str, Path], tmp_path: Path, policy: str
) -> None:
    _set_cap(tmp_path, "1.0")
    inner = _step_type(f"_cap_each_{next(_step_names)}")
    definition = PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="each",
                name="batch",
                config={
                    "source": "cf.unfinished_slices()",
                    "as": "slice",
                    "on_item_failure": policy,
                    "steps": [{inner: {}}],
                },
            )
        ],
    )
    cf_client = MagicMock()
    cf_client.list_slices.return_value = [
        SliceEntry(index=i, name=f"slice-{i}", design_file=None, status="not_started")
        for i in range(1, 6)
    ]
    action = _priced_action(0.4)

    result = await _run(definition, action, tmp_path, cf_client=cf_client)

    assert result.status is ExecutionStatus.FAILED
    assert action.execute.await_count == 3  # items 4 and 5 never ran
