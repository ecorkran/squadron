"""Tests for slice 244 — conditional SDKExecutionSession construction.

Covers:
- T3: _run_pipeline backward-compatible fallback (no pool_backend arg)
- T6: Classification gate in _run_pipeline_sdk (T1–T5, T3b, T8 from design)
- T7: Resume path classification (T6, T7 from design)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.run import _run_pipeline
from squadron.pipeline.classification import (
    ClassificationError,
    PipelineClassification,
    PipelineShape,
    StepClass,
    StepClassification,
)
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_definition(
    name: str = "test-pipeline",
    steps: list[StepConfig] | None = None,
) -> PipelineDefinition:
    return PipelineDefinition(
        name=name,
        description="Test pipeline",
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
) -> PipelineClassification:
    """Return a MagicMock with PipelineClassification interface."""
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
    return mock  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# T3: _run_pipeline backward-compatible fallback (no pool_backend arg)
# ---------------------------------------------------------------------------


class TestRunPipelinePoolBackendFallback:
    """_run_pipeline constructs DefaultPoolBackend internally when not supplied."""

    def test_fallback_constructs_default_pool_backend(self, tmp_path: Path) -> None:
        """Calling _run_pipeline without pool_backend triggers internal construction."""
        mock_result = _make_result()

        with (
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run._check_cf"),
            patch(
                "squadron.cli.commands.run.execute_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_execute,
            patch("squadron.cli.commands.run.DefaultPoolBackend") as mock_backend_cls,
        ):
            mgr = StateManager(runs_dir=tmp_path)
            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
                asyncio.run(_run_pipeline("test-pipeline", {}, runs_dir=tmp_path))

        mock_backend_cls.assert_called_once()
        mock_execute.assert_awaited_once()

    def test_supplied_pool_backend_skips_internal_construction(self, tmp_path: Path) -> None:
        """Supplying pool_backend skips internal DefaultPoolBackend construction."""
        from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend

        mock_result = _make_result()
        supplied_backend = DefaultPoolBackend()

        with (
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch("squadron.cli.commands.run._check_cf"),
            patch(
                "squadron.cli.commands.run.execute_pipeline",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_execute,
            patch("squadron.cli.commands.run.DefaultPoolBackend") as mock_backend_cls,
        ):
            mgr = StateManager(runs_dir=tmp_path)
            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
                asyncio.run(
                    _run_pipeline(
                        "test-pipeline",
                        {},
                        runs_dir=tmp_path,
                        pool_backend=supplied_backend,
                    )
                )

        mock_backend_cls.assert_not_called()
        mock_execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# T6: Classification gate in _run_pipeline_sdk
# ---------------------------------------------------------------------------


def _sdk_patches(
    classification: PipelineClassification,
    session_mock: Any | None = None,
) -> tuple[Any, ...]:
    """Return a tuple of patch context managers for _run_pipeline_sdk tests."""
    patches: list[Any] = [
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
    ]
    if session_mock is not None:
        patches.append(
            patch(
                "squadron.cli.commands.run.SDKExecutionSession",
                return_value=session_mock,
            )
        )
        patches.append(patch("claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()))
        patches.append(patch("claude_agent_sdk.ClaudeSDKClient", return_value=MagicMock()))
    else:
        patches.append(patch("squadron.cli.commands.run.SDKExecutionSession"))
    return tuple(patches)


_PATCH_RESOLVE_EXEC_MODE = patch("squadron.cli.commands.run._resolve_execution_mode")


class TestClassificationGate:
    """_run_pipeline_sdk gates SDKExecutionSession on classification result."""

    def _run_sdk(self, **kwargs: Any) -> PipelineResult:
        from squadron.cli.commands.run import _run_pipeline_sdk

        return asyncio.run(_run_pipeline_sdk("test-pipeline", {}, **kwargs))

    def test_t1_claude_free_no_session(self) -> None:
        """All steps non-SDK: SDKExecutionSession never constructed."""
        classification = _make_classification(
            needs_persistent=False,
            shape=PipelineShape.CLAUDE_FREE,
        )

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ) as mock_run,
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            self._run_sdk()

        mock_session_cls.assert_not_called()
        _, kwargs = mock_run.call_args
        assert kwargs.get("sdk_session") is None

    def test_t2_non_sdk_pipeline_no_session(self) -> None:
        """Non-SDK pipeline (summary+compact covered by shape): no session, no crash."""
        classification = _make_classification(
            needs_persistent=False,
            shape=PipelineShape.CLAUDE_FREE,
        )

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            result = self._run_sdk()

        assert result.status == ExecutionStatus.COMPLETED
        mock_session_cls.assert_not_called()

    def test_t3_sdk_dispatch_step_constructs_session(self) -> None:
        """At least one SDK dispatch step: session constructed and connect() called."""
        classification = _make_classification(
            needs_persistent=True,
            shape=PipelineShape.CLAUDE_REQUIRED_PERSISTENT,
            step_class=StepClass.SDK_REQUIRED,
        )
        mock_session = AsyncMock()
        mock_session.connect = AsyncMock()
        mock_session.disconnect = AsyncMock()

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch(
                "squadron.cli.commands.run.SDKExecutionSession",
                return_value=mock_session,
            ),
            patch("claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()),
            patch("claude_agent_sdk.ClaudeSDKClient", return_value=MagicMock()),
        ):
            self._run_sdk()

        mock_session.connect.assert_awaited_once()
        mock_session.disconnect.assert_awaited_once()

    def test_t3b_one_shot_shape_no_persistent_session(self) -> None:
        """claude_required_one_shot: no persistent session; sdk_session=None passed."""
        one_shot_step = StepClassification(
            step_name="review1",
            step_index=0,
            action_type="review",
            resolved_alias="sonnet",
            resolved_model_id="claude-sonnet-4-5",
            profile="sdk",
            classification=StepClass.SDK_REQUIRED,
            rationale="review step uses one-shot path",
        )
        classification = MagicMock(spec=PipelineClassification)
        classification.needs_persistent_session = False
        classification.needs_one_shot_claude = True
        classification.shape = PipelineShape.CLAUDE_REQUIRED_ONE_SHOT
        classification.steps = (one_shot_step,)

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ) as mock_run,
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            self._run_sdk()

        mock_session_cls.assert_not_called()
        _, kwargs = mock_run.call_args
        assert kwargs.get("sdk_session") is None

    def test_t4_pool_uncertain_constructs_session(self) -> None:
        """POOL_UNCERTAIN step: conservative path — session constructed."""
        classification = _make_classification(
            needs_persistent=True,
            shape=PipelineShape.CLAUDE_REQUIRED_PERSISTENT,
            step_class=StepClass.POOL_UNCERTAIN,
        )
        mock_session = AsyncMock()
        mock_session.connect = AsyncMock()
        mock_session.disconnect = AsyncMock()

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch(
                "squadron.cli.commands.run.SDKExecutionSession",
                return_value=mock_session,
            ),
            patch("claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()),
            patch("claude_agent_sdk.ClaudeSDKClient", return_value=MagicMock()),
        ):
            self._run_sdk()

        mock_session.connect.assert_awaited_once()

    def test_t5_classification_error_exits_1(self) -> None:
        """ClassificationError produces typer.Exit(1); no session created."""
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
                side_effect=ClassificationError("bad cascade"),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            with pytest.raises(typer.Exit) as exc_info:
                self._run_sdk()

        assert exc_info.value.exit_code == 1
        mock_session_cls.assert_not_called()

    def test_t8_connect_failure_propagates_no_disconnect(self) -> None:
        """connect() failure: exception propagates; disconnect() never called."""
        from claude_agent_sdk import CLINotFoundError

        classification = _make_classification(
            needs_persistent=True,
            shape=PipelineShape.CLAUDE_REQUIRED_PERSISTENT,
            step_class=StepClass.SDK_REQUIRED,
        )
        mock_session = AsyncMock()
        mock_session.connect = AsyncMock(side_effect=CLINotFoundError("claude not found"))
        mock_session.disconnect = AsyncMock()

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch("squadron.cli.commands.run._run_pipeline", new_callable=AsyncMock),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch(
                "squadron.cli.commands.run.SDKExecutionSession",
                return_value=mock_session,
            ),
            patch("claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()),
            patch("claude_agent_sdk.ClaudeSDKClient", return_value=MagicMock()),
        ):
            with pytest.raises(CLINotFoundError):
                self._run_sdk()

        mock_session.connect.assert_awaited_once()
        mock_session.disconnect.assert_not_awaited()


# ---------------------------------------------------------------------------
# T7: Resume path
# ---------------------------------------------------------------------------


class TestResumePath:
    """Resume re-classifies and gates session on each call."""

    def test_t6_resume_non_sdk_no_session(self) -> None:
        """Resume with non-SDK classification: no session constructed."""
        from squadron.cli.commands.run import _run_pipeline_sdk

        classification = _make_classification(
            needs_persistent=False,
            shape=PipelineShape.CLAUDE_FREE,
        )

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
        ):
            asyncio.run(
                _run_pipeline_sdk(
                    "test-pipeline",
                    {"model": "sonnet"},
                    run_id="run-resume-001",
                    from_step="step1",
                )
            )

        mock_session_cls.assert_not_called()

    def test_t7_resume_sdk_constructs_session(self) -> None:
        """Resume with SDK classification: session constructed and connected."""
        from squadron.cli.commands.run import _run_pipeline_sdk

        classification = _make_classification(
            needs_persistent=True,
            shape=PipelineShape.CLAUDE_REQUIRED_PERSISTENT,
            step_class=StepClass.SDK_REQUIRED,
        )
        mock_session = AsyncMock()
        mock_session.connect = AsyncMock()
        mock_session.disconnect = AsyncMock()

        with (
            _PATCH_RESOLVE_EXEC_MODE,
            patch(
                "squadron.cli.commands.run.load_pipeline",
                return_value=_make_definition(),
            ),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
            patch(
                "squadron.cli.commands.run.classify_pipeline",
                return_value=classification,
            ),
            patch(
                "squadron.cli.commands.run._run_pipeline",
                new_callable=AsyncMock,
                return_value=_make_result(),
            ),
            patch("squadron.cli.commands.run.DefaultPoolBackend", return_value=MagicMock()),
            patch("squadron.cli.commands.run.ModelResolver", return_value=MagicMock()),
            patch(
                "squadron.cli.commands.run.SDKExecutionSession",
                return_value=mock_session,
            ),
            patch("claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()),
            patch("claude_agent_sdk.ClaudeSDKClient", return_value=MagicMock()),
        ):
            asyncio.run(
                _run_pipeline_sdk(
                    "test-pipeline",
                    {"model": "sonnet"},
                    run_id="run-resume-002",
                    from_step="step1",
                )
            )

        mock_session.connect.assert_awaited_once()
        mock_session.disconnect.assert_awaited_once()
