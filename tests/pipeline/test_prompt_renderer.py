"""Tests for prompt_renderer data models, builders, and render_step_instructions."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import StepConfig
from squadron.pipeline.prompt_renderer import (
    ActionInstruction,
    CompletionResult,
    StepInstructions,
    _render_cf_op,
    _render_checkpoint,
    _render_commit,
    _render_compact,
    _render_devlog,
    _render_dispatch,
    _render_review,
    _render_summary,
    render_step_instructions,
)

# ---------------------------------------------------------------------------
# T2: Data model tests
# ---------------------------------------------------------------------------


class TestActionInstruction:
    def test_round_trip_through_asdict_and_json(self) -> None:
        ai = ActionInstruction(
            action_type="cf-op",
            instruction="Set phase to 4",
            command="cf set phase 4",
        )
        d = asdict(ai)
        raw = json.dumps(d)
        restored = json.loads(raw)
        assert restored["action_type"] == "cf-op"
        assert restored["command"] == "cf set phase 4"

    def test_optional_fields_serialize_as_null(self) -> None:
        ai = ActionInstruction(action_type="dispatch", instruction="Do work")
        d = asdict(ai)
        assert d["command"] is None
        assert d["model"] is None
        assert d["model_switch"] is None
        assert d["template"] is None
        assert d["trigger"] is None
        assert d["resolved_instructions"] is None
        assert d["emit"] is None

    def test_all_fields_populated(self) -> None:
        ai = ActionInstruction(
            action_type="compact",
            instruction="Compact context",
            command="/compact [instructions]",
            model="sonnet",
            model_switch="/model sonnet",
            template="minimal",
            trigger=None,
            resolved_instructions="Keep slice design for 152",
        )
        d = asdict(ai)
        raw = json.dumps(d)
        restored = json.loads(raw)
        assert restored["resolved_instructions"] == "Keep slice design for 152"
        assert restored["template"] == "minimal"


class TestStepInstructions:
    def test_to_json_produces_valid_json(self) -> None:
        si = StepInstructions(
            run_id="run-20260403-slice-abc12345",
            step_name="design-0",
            step_type="design",
            step_index=0,
            total_steps=6,
            actions=[
                ActionInstruction(
                    action_type="cf-op",
                    instruction="Set phase to 4",
                    command="cf set phase 4",
                ),
            ],
        )
        raw = si.to_json()
        parsed = json.loads(raw)
        assert parsed["run_id"] == "run-20260403-slice-abc12345"
        assert parsed["step_name"] == "design-0"
        assert parsed["total_steps"] == 6
        assert len(parsed["actions"]) == 1
        assert parsed["actions"][0]["action_type"] == "cf-op"

    def test_empty_actions_list(self) -> None:
        si = StepInstructions(
            run_id="r1",
            step_name="s",
            step_type="t",
            step_index=0,
            total_steps=1,
            actions=[],
        )
        parsed = json.loads(si.to_json())
        assert parsed["actions"] == []


class TestCompletionResult:
    def test_serializes_correctly(self) -> None:
        cr = CompletionResult(
            status="completed",
            message="All steps complete",
            run_id="run-abc",
        )
        parsed = json.loads(cr.to_json())
        assert parsed["status"] == "completed"
        assert parsed["message"] == "All steps complete"
        assert parsed["run_id"] == "run-abc"


# ---------------------------------------------------------------------------
# T4: Action instruction builder tests
# ---------------------------------------------------------------------------


def _make_resolver(model_id: str = "resolved-model") -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, None)
    return resolver


class TestRenderCfOp:
    def test_set_phase(self) -> None:
        result = _render_cf_op({"operation": "set_phase", "phase": 4}, {})
        assert result.action_type == ActionType.CF_OP
        assert result.command == "cf set phase 4"
        assert "4" in result.instruction

    def test_build_context(self) -> None:
        result = _render_cf_op({"operation": "build_context"}, {})
        assert result.command == "cf build"

    def test_summarize(self) -> None:
        result = _render_cf_op({"operation": "summarize"}, {})
        assert result.command == "cf summarize"

    def test_unknown_operation(self) -> None:
        result = _render_cf_op({"operation": "something_else"}, {})
        assert result.command == "cf something_else"


class TestRenderDispatch:
    def test_with_model(self) -> None:
        resolver = _make_resolver("claude-opus-4-20250514")
        result = _render_dispatch({"model": "opus"}, {}, resolver)
        assert result.action_type == ActionType.DISPATCH
        assert result.model == "claude-opus-4-20250514"
        assert result.model_switch == "/model opus"
        assert result.command is None

    def test_without_model(self) -> None:
        resolver = _make_resolver()
        result = _render_dispatch({"model": None}, {}, resolver)
        assert result.model is None
        assert result.model_switch is None


class TestRenderReview:
    def test_includes_template_and_model(self) -> None:
        resolver = _make_resolver("glm5-resolved")
        result = _render_review(
            {"template": "slice", "model": "glm5"},
            {"slice": "152"},
            resolver,
        )
        assert result.action_type == ActionType.REVIEW
        assert result.template == "slice"
        assert result.model == "glm5-resolved"
        assert "--template" not in result.command
        assert "--model glm5" in result.command
        assert "--model glm5-resolved" not in result.command
        assert "152" in result.command
        assert result.command == "sq review slice 152 --model glm5 -v"


class TestRenderCheckpoint:
    @pytest.mark.parametrize(
        "trigger",
        ["on-concerns", "on-fail", "always", "never"],
    )
    def test_trigger_types(self, trigger: str) -> None:
        result = _render_checkpoint({"trigger": trigger}, {})
        assert result.action_type == ActionType.CHECKPOINT
        assert result.trigger == trigger

    def test_default_trigger(self) -> None:
        result = _render_checkpoint({}, {})
        assert result.trigger == "on-concerns"


class TestRenderCommit:
    def test_with_message_prefix(self) -> None:
        result = _render_commit({"message_prefix": "phase-4"}, {})
        assert result.action_type == ActionType.COMMIT
        assert "phase-4" in result.command
        assert "git add -A" in result.command

    def test_without_prefix(self) -> None:
        result = _render_commit({}, {})
        assert "chore" in result.command


class TestRenderCompact:
    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
    @patch("squadron.pipeline.prompt_renderer.render_instructions")
    def test_resolves_pipeline_params(
        self, mock_render: MagicMock, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = MagicMock()
        mock_render.return_value = "Keep slice design for 152"

        result = _render_compact({"template": "minimal"}, {"slice": "152"})
        assert result.action_type == ActionType.COMPACT
        assert result.template == "minimal"
        assert result.resolved_instructions == "Keep slice design for 152"
        assert "/compact [Keep slice design for 152]" == result.command

        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args
        assert call_kwargs.kwargs["pipeline_params"]["slice"] == "152"

    def test_missing_template(self) -> None:
        # Uses real loader — nonexistent template
        result = _render_compact({"template": "nonexistent_xyz"}, {})
        assert "not found" in result.resolved_instructions


class TestRenderDevlog:
    def test_auto_mode(self) -> None:
        result = _render_devlog({"mode": "auto"}, {})
        assert result.action_type == ActionType.DEVLOG
        assert "auto" in result.instruction

    def test_default_mode(self) -> None:
        result = _render_devlog({}, {})
        assert "auto" in result.instruction


class TestRenderSummary:
    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
    @patch("squadron.pipeline.prompt_renderer.render_instructions")
    def test_with_model_and_emit(
        self, mock_render: MagicMock, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = MagicMock()
        mock_render.return_value = "Summarize recent work"
        resolver = _make_resolver("minimax-resolved")

        result = _render_summary(
            {
                "template": "minimal-sdk",
                "model": "minimax",
                "emit": ["stdout", "clipboard"],
            },
            {"slice": "165"},
            resolver,
        )

        assert result.action_type == ActionType.SUMMARY
        assert result.template == "minimal-sdk"
        assert result.model == "minimax-resolved"
        assert result.model_switch == "/model minimax"
        assert result.resolved_instructions == "Summarize recent work"
        assert result.emit == ["stdout", "clipboard"]
        assert result.command is None  # no shell command

    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
    @patch("squadron.pipeline.prompt_renderer.render_instructions")
    def test_without_model_or_emit(
        self, mock_render: MagicMock, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = MagicMock()
        mock_render.return_value = "instructions"
        resolver = _make_resolver()

        result = _render_summary({}, {}, resolver)
        assert result.model is None
        assert result.model_switch is None
        assert result.emit is None

    def test_missing_template(self) -> None:
        resolver = _make_resolver()
        result = _render_summary({"template": "nonexistent_xyz"}, {}, resolver)
        assert "not found" in result.resolved_instructions

    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
    @patch("squadron.pipeline.prompt_renderer.render_instructions")
    def test_emit_with_rotate(
        self, mock_render: MagicMock, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = MagicMock()
        mock_render.return_value = "instructions"
        resolver = _make_resolver()

        result = _render_summary(
            {"template": "minimal-sdk", "emit": ["rotate"]}, {}, resolver
        )
        assert result.emit == ["rotate"]


class TestFallbackUnknownAction:
    def test_unknown_type_returns_generic_instruction(self) -> None:
        from squadron.pipeline.prompt_renderer import _build_action_instruction

        resolver = _make_resolver()
        result = _build_action_instruction("mystery-action", {}, {}, resolver)
        assert result.action_type == "mystery-action"
        assert "mystery-action" in result.instruction


# ---------------------------------------------------------------------------
# T6: render_step_instructions tests
# ---------------------------------------------------------------------------


class TestRenderStepInstructions:
    def test_design_phase_step(self) -> None:
        """Design step with phase 4, model opus, review slice/glm5, checkpoint."""
        resolver = MagicMock()

        def _resolve(
            action_model: str | None = None, step_model: str | None = None
        ) -> tuple[str, str | None]:
            models = {"opus": "claude-opus-4-20250514", "glm5": "glm5-resolved"}
            if action_model and action_model in models:
                return (models[action_model], None)
            return ("default-model", None)

        resolver.resolve.side_effect = _resolve

        step = StepConfig(
            step_type="design",
            name="design-0",
            config={
                "phase": 4,
                "model": "opus",
                "review": {"template": "slice", "model": "glm5"},
                "checkpoint": "on-concerns",
            },
        )

        result = render_step_instructions(
            step,
            step_index=0,
            total_steps=6,
            params={"slice": "152"},
            resolver=resolver,
            run_id="run-test",
        )

        assert result.run_id == "run-test"
        assert result.step_name == "design-0"
        assert result.step_type == "design"
        assert result.step_index == 0
        assert result.total_steps == 6

        # 7 actions: set_phase, set_slice, build, dispatch, review, checkpoint, commit
        assert len(result.actions) == 7

        types = [a.action_type for a in result.actions]
        assert types == [
            "cf-op",
            "cf-op",
            "cf-op",
            "dispatch",
            "review",
            "checkpoint",
            "commit",
        ]

        # set_slice resolves {slice} param
        set_slice = result.actions[1]
        assert set_slice.command == "cf set slice 152"

        # Dispatch has opus model
        dispatch = result.actions[3]
        assert dispatch.model == "claude-opus-4-20250514"
        assert dispatch.model_switch == "/model opus"

        # Review has slice template and glm5 model
        review = result.actions[4]
        assert review.template == "slice"
        assert review.model == "glm5-resolved"

        # Checkpoint has on-concerns trigger
        checkpoint = result.actions[5]
        assert checkpoint.trigger == "on-concerns"

    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
    @patch("squadron.pipeline.prompt_renderer.render_instructions")
    def test_compact_step(self, mock_render: MagicMock, mock_load: MagicMock) -> None:
        """Compact step with template and resolved params."""
        mock_load.return_value = MagicMock()
        mock_render.return_value = "Keep design for slice 152"
        resolver = _make_resolver()

        step = StepConfig(
            step_type="compact",
            name="compact-2",
            config={"template": "minimal"},
        )

        result = render_step_instructions(
            step,
            step_index=2,
            total_steps=6,
            params={"slice": "152"},
            resolver=resolver,
            run_id="run-test",
        )

        assert len(result.actions) == 1
        compact = result.actions[0]
        assert compact.action_type == "compact"
        assert "152" in compact.resolved_instructions or mock_render.called

    def test_devlog_step(self) -> None:
        """Devlog step with auto mode."""
        resolver = _make_resolver()

        step = StepConfig(
            step_type="devlog",
            name="devlog-5",
            config={"mode": "auto"},
        )

        result = render_step_instructions(
            step,
            step_index=5,
            total_steps=6,
            params={"slice": "152"},
            resolver=resolver,
            run_id="run-test",
        )

        assert len(result.actions) == 1
        assert result.actions[0].action_type == "devlog"
        assert "auto" in result.actions[0].instruction

    def test_step_without_review(self) -> None:
        """Phase step without review omits review/checkpoint."""
        resolver = _make_resolver()

        step = StepConfig(
            step_type="design",
            name="design-0",
            config={"phase": 4, "model": "sonnet"},
        )

        result = render_step_instructions(
            step,
            step_index=0,
            total_steps=1,
            params={},
            resolver=resolver,
            run_id="run-test",
        )

        types = [a.action_type for a in result.actions]
        assert "review" not in types
        assert "checkpoint" not in types
        # set_phase, set_slice, build, dispatch, commit
        assert len(result.actions) == 5

    def test_to_json_round_trip(self) -> None:
        """Verify the full output can round-trip through JSON."""
        resolver = _make_resolver()

        step = StepConfig(
            step_type="devlog",
            name="devlog-0",
            config={"mode": "auto"},
        )

        result = render_step_instructions(
            step,
            step_index=0,
            total_steps=1,
            params={},
            resolver=resolver,
            run_id="run-test",
        )

        raw = result.to_json()
        parsed = json.loads(raw)
        assert parsed["step_name"] == "devlog-0"
        assert len(parsed["actions"]) == 1
