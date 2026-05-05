"""Tests for slice 245 — lazy pool-auth default; --strict opt-in; mid-run session construction.

Covers:
- T10: mid-run session construction hook in execute_pipeline
- T10c: dispatch-action guard (pool resolves SDK at runtime, no session)
- T12: mid-run connect failure UX
- T14: --strict flag and policy resolution in _run_pipeline_sdk
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.run import _run_pipeline_sdk
from squadron.pipeline.classification import (
    PipelineClassification,
    PipelineShape,
    PoolClassificationPolicy,
    StepClass,
    StepClassification,
)
from squadron.pipeline.executor import (
    ExecutionStatus,
    LazySessionConnectError,
    PipelineResult,
    _step_needs_sdk,
    execute_pipeline,
)
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ModelResolver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_definition(
    steps: list[StepConfig] | None = None,
    name: str = "test-pipeline",
) -> PipelineDefinition:
    return PipelineDefinition(
        name=name,
        description="test",
        params={},
        steps=steps or [StepConfig(step_type="dispatch", name="step1", config={"model": "sonnet"})],
    )


def _make_result(pipeline_name: str = "test-pipeline") -> PipelineResult:
    return PipelineResult(
        pipeline_name=pipeline_name,
        status=ExecutionStatus.COMPLETED,
        step_results=[],
    )


def _make_classification(
    needs_persistent: bool,
    shape: PipelineShape,
    step_class: StepClass = StepClass.NON_SDK,
    policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
) -> PipelineClassification:
    step = StepClassification(
        step_name="step1",
        step_index=0,
        action_type="dispatch",
        resolved_alias="sonnet",
        resolved_model_id="claude-sonnet-4-5",
        profile="sdk" if step_class == StepClass.SDK_REQUIRED else "minimax",
        classification=step_class,
        rationale="test",
    )
    mock = MagicMock(spec=PipelineClassification)
    mock.needs_persistent_session = needs_persistent
    mock.shape = shape
    mock.steps = (step,)
    mock.policy = policy
    return mock  # type: ignore[return-value]


_PATCH_RESOLVE_EXEC_MODE = patch("squadron.cli.commands.run._resolve_execution_mode")


def _sdk_base_patches(
    classification: PipelineClassification,
) -> tuple[Any, ...]:
    return (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_make_definition()),
        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        patch("squadron.cli.commands.run.classify_pipeline", return_value=classification),
        patch(
            "squadron.cli.commands.run._run_pipeline",
            new_callable=AsyncMock,
            return_value=_make_result(),
        ),
        patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
        patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
        patch("squadron.cli.commands.run.SDKExecutionSession"),
    )


# ---------------------------------------------------------------------------
# T10 — _step_needs_sdk unit tests
# ---------------------------------------------------------------------------


class TestStepNeedsSdk:
    """Unit tests for the _step_needs_sdk helper."""

    def _make_resolver(self, config_default: str | None = None) -> ModelResolver:
        return ModelResolver(config_default=config_default)

    def test_returns_true_for_sdk_alias(self) -> None:
        step = StepConfig(step_type="dispatch", name="s", config={"model": "sonnet"})
        resolver = self._make_resolver()
        assert _step_needs_sdk(step, resolver, {}) is True

    def test_returns_false_for_non_sdk_alias(self) -> None:
        step = StepConfig(step_type="dispatch", name="s", config={"model": "minimax"})
        resolver = self._make_resolver()
        assert _step_needs_sdk(step, resolver, {}) is False

    def test_returns_false_for_pool_candidate(self) -> None:
        step = StepConfig(step_type="dispatch", name="s", config={"model": "pool:review"})
        resolver = self._make_resolver()
        assert _step_needs_sdk(step, resolver, {}) is False

    def test_returns_false_for_non_persistent_step_type(self) -> None:
        # review steps use one-shot path, not persistent session
        step = StepConfig(step_type="review", name="s", config={"model": "sonnet"})
        resolver = self._make_resolver()
        assert _step_needs_sdk(step, resolver, {}) is False

    def test_returns_false_for_checkpoint_step(self) -> None:
        step = StepConfig(step_type="checkpoint", name="s", config={})
        resolver = self._make_resolver()
        assert _step_needs_sdk(step, resolver, {}) is False


# ---------------------------------------------------------------------------
# T10 — mid-run hook integration tests (via execute_pipeline)
# ---------------------------------------------------------------------------


class TestMidRunSessionHook:
    """execute_pipeline lazily connects a session before the first SDK step."""

    def _make_action_registry(self) -> dict[str, Any]:
        """Return a minimal registry that succeeds for dispatch steps."""
        mock_action = AsyncMock()
        mock_action.action_type = "dispatch"
        mock_action.validate = MagicMock(return_value=[])
        mock_action.execute = AsyncMock(
            return_value=ActionResult(
                success=True,
                action_type="dispatch",
                outputs={"response": "ok"},
            )
        )
        return {"dispatch": mock_action}

    def _make_cf_client(self) -> Any:
        mock = MagicMock()
        mock.get_project = MagicMock(return_value={"project": "test"})
        return mock

    @pytest.mark.asyncio
    async def test_no_sdk_steps_no_session_constructed(self) -> None:
        """Pipeline with only non-SDK steps: _connect_lazy_session never called."""
        definition = _make_definition(
            steps=[StepConfig(step_type="dispatch", name="s1", config={"model": "minimax"})]
        )
        resolver = ModelResolver()
        action_registry = self._make_action_registry()
        action_registry["dispatch"].execute = AsyncMock(
            return_value=ActionResult(
                success=True,
                action_type="dispatch",
                outputs={},
            )
        )

        with patch(
            "squadron.pipeline.executor._connect_lazy_session", new_callable=AsyncMock
        ) as mock_connect:
            await execute_pipeline(
                definition,
                {},
                resolver=resolver,
                cf_client=self._make_cf_client(),
                pool_policy=PoolClassificationPolicy.LAZY,
                _action_registry=action_registry,
            )

        mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_static_sdk_step_constructs_session(self) -> None:
        """Pipeline with a static SDK step: _connect_lazy_session called once."""
        definition = _make_definition(
            steps=[StepConfig(step_type="dispatch", name="s1", config={"model": "sonnet"})]
        )
        resolver = ModelResolver()
        action_registry = self._make_action_registry()
        mock_session = MagicMock()

        with patch(
            "squadron.pipeline.executor._connect_lazy_session",
            new_callable=AsyncMock,
            return_value=mock_session,
        ) as mock_connect:
            await execute_pipeline(
                definition,
                {},
                resolver=resolver,
                cf_client=self._make_cf_client(),
                pool_policy=PoolClassificationPolicy.LAZY,
                _action_registry=action_registry,
            )

        mock_connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_sdk_steps_reuse_same_session(self) -> None:
        """Two SDK steps: _connect_lazy_session called exactly once."""
        definition = _make_definition(
            steps=[
                StepConfig(step_type="dispatch", name="s1", config={"model": "sonnet"}),
                StepConfig(step_type="dispatch", name="s2", config={"model": "sonnet"}),
            ]
        )
        resolver = ModelResolver()
        action_registry = self._make_action_registry()
        mock_session = MagicMock()

        with patch(
            "squadron.pipeline.executor._connect_lazy_session",
            new_callable=AsyncMock,
            return_value=mock_session,
        ) as mock_connect:
            await execute_pipeline(
                definition,
                {},
                resolver=resolver,
                cf_client=self._make_cf_client(),
                pool_policy=PoolClassificationPolicy.LAZY,
                _action_registry=action_registry,
            )

        mock_connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lazy_pool_uncertain_only_no_session_at_startup(self, tmp_path: Path) -> None:
        """POOL_UNCERTAIN-only pipeline under LAZY: SDKExecutionSession constructor never called."""
        definition = _make_definition(
            steps=[
                StepConfig(step_type="dispatch", name="pool-step", config={"model": "pool:mixed-pool"})
            ]
        )
        mock_result = _make_result()

        with (
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=definition,
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=_make_classification(
                    needs_persistent=False,
                    shape=PipelineShape.CLAUDE_FREE,
                    policy=PoolClassificationPolicy.LAZY,
                ),
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
            _PATCH_RESOLVE_EXEC_MODE,
        ):
            await _run_pipeline_sdk("test-pipeline", {})

        mock_session_cls.assert_not_called()


# ---------------------------------------------------------------------------
# T10c — dispatch-action guard
# ---------------------------------------------------------------------------


class TestDispatchActionGuard:
    """Pool resolves SDK at runtime but no session available → FAILED with --strict hint."""

    def _make_context(self, *, sdk_session: Any = None, model: str = "sonnet") -> ActionContext:
        resolver = ModelResolver()
        return ActionContext(
            pipeline_name="test",
            run_id="r1",
            params={"model": model, "prompt": "hello"},
            step_name="pool-dispatch",
            step_index=0,
            prior_outputs={},
            resolver=resolver,
            cf_client=MagicMock(),
            cwd="/tmp",
            sdk_session=sdk_session,
        )

    @pytest.mark.asyncio
    async def test_dispatch_sdk_profile_no_session_returns_failed(self) -> None:
        from squadron.pipeline.actions.dispatch import DispatchAction

        ctx = self._make_context(sdk_session=None, model="sonnet")
        action = DispatchAction()
        result = await action.execute(ctx)
        assert result.success is False
        assert result.error is not None
        assert "--strict" in result.error

    @pytest.mark.asyncio
    async def test_dispatch_non_sdk_no_session_uses_agent_path(self) -> None:
        """Non-SDK profile with no session routes to agent path (not blocked by guard)."""
        from squadron.pipeline.actions.dispatch import DispatchAction

        ctx = self._make_context(sdk_session=None, model="minimax")
        action = DispatchAction()
        with patch.object(action, "_dispatch_via_agent", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = ActionResult(
                success=True,
                action_type="dispatch",
                outputs={"response": "ok"},
            )
            result = await action.execute(ctx)
        assert result.success is True
        mock_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_sdk_profile_with_session_proceeds(self) -> None:
        """SDK profile with a connected session routes normally (no guard FAILED)."""
        from squadron.pipeline.actions.dispatch import DispatchAction

        mock_session = AsyncMock()
        ctx = self._make_context(sdk_session=mock_session, model="sonnet")
        action = DispatchAction()
        with patch.object(action, "_dispatch_via_session", new_callable=AsyncMock) as mock_sess:
            mock_sess.return_value = ActionResult(
                success=True,
                action_type="dispatch",
                outputs={"response": "ok"},
            )
            result = await action.execute(ctx)
        assert result.success is True
        mock_sess.assert_awaited_once()


# ---------------------------------------------------------------------------
# T12 — mid-run connect failure UX
# ---------------------------------------------------------------------------


class TestLazyConnectFailureUX:
    """When _connect_lazy_session raises, state is saved as failed and typer.Exit(1) raised."""

    def _make_lazy_classification(self) -> PipelineClassification:
        return _make_classification(
            needs_persistent=False,
            shape=PipelineShape.CLAUDE_FREE,
            policy=PoolClassificationPolicy.LAZY,
        )

    @pytest.mark.asyncio
    async def test_lazy_connect_failure_raises_typer_exit_1(self, tmp_path: Path) -> None:
        import typer

        from squadron.cli.commands.run import _run_pipeline_sdk

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=self._make_lazy_classification(),
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                side_effect=LazySessionConnectError("step1", RuntimeError("auth failed")),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                await _run_pipeline_sdk("test-pipeline", {})

        assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_lazy_connect_failure_message_names_step(self, tmp_path: Path, capsys: Any) -> None:
        import typer

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=self._make_lazy_classification(),
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                side_effect=LazySessionConnectError("my-step", RuntimeError("connection refused")),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
            patch("squadron.cli.commands.run.rprint") as mock_rprint,
        ):
            with pytest.raises(typer.Exit):
                await _run_pipeline_sdk("test-pipeline", {})

        # The printed message should mention the triggering step name.
        printed = " ".join(str(a) for call in mock_rprint.call_args_list for a in call[0])
        assert "my-step" in printed


# ---------------------------------------------------------------------------
# T14 — --strict flag and policy resolution
# ---------------------------------------------------------------------------


class TestStrictFlagAndPolicyResolution:
    """_run_pipeline_sdk resolves policy correctly from strict flag and YAML auth_policy."""

    def _run_sdk(self, **kwargs: Any) -> PipelineResult:
        return asyncio.run(_run_pipeline_sdk("test-pipeline", {}, **kwargs))

    def test_strict_flag_passes_strict_policy_to_classify(self) -> None:
        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=_make_classification(
                    needs_persistent=False,
                    shape=PipelineShape.CLAUDE_FREE,
                    policy=PoolClassificationPolicy.STRICT,
                ),
            ) as mock_classify,
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
        ):
            self._run_sdk(strict=True)

        _, kwargs = mock_classify.call_args
        assert kwargs.get("policy") == PoolClassificationPolicy.STRICT

    def test_no_flag_passes_lazy_policy_to_classify(self) -> None:
        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=_make_classification(
                    needs_persistent=False,
                    shape=PipelineShape.CLAUDE_FREE,
                    policy=PoolClassificationPolicy.LAZY,
                ),
            ) as mock_classify,
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
        ):
            self._run_sdk(strict=False)

        _, kwargs = mock_classify.call_args
        assert kwargs.get("policy") == PoolClassificationPolicy.LAZY

    def test_yaml_auth_policy_strict_overrides_lazy_default(self) -> None:
        definition = _make_definition()
        definition.auth_policy = "strict"

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=_make_classification(
                    needs_persistent=False,
                    shape=PipelineShape.CLAUDE_FREE,
                    policy=PoolClassificationPolicy.STRICT,
                ),
            ) as mock_classify,
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
        ):
            self._run_sdk(strict=False)

        _, kwargs = mock_classify.call_args
        assert kwargs.get("policy") == PoolClassificationPolicy.STRICT

    def test_cli_strict_flag_overrides_yaml_lazy(self) -> None:
        definition = _make_definition()
        definition.auth_policy = "lazy"

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=_make_classification(
                    needs_persistent=False,
                    shape=PipelineShape.CLAUDE_FREE,
                    policy=PoolClassificationPolicy.STRICT,
                ),
            ) as mock_classify,
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession"),
        ):
            self._run_sdk(strict=True)

        _, kwargs = mock_classify.call_args
        assert kwargs.get("policy") == PoolClassificationPolicy.STRICT
