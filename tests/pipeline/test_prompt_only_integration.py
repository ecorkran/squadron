"""Integration test — full prompt-only pipeline cycle.

Exercises the complete init → step-done → next → ... → completion flow
using the real StateManager, pipeline loader, and prompt renderer.
"""

from __future__ import annotations

import json
from pathlib import Path

from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.prompt_renderer import (
    CompletionResult,
    render_step_instructions,
)
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.state import StateManager


def _load_slice_pipeline() -> object:
    """Load the built-in 'slice' pipeline, bypassing project/user dirs."""
    return load_pipeline(
        "slice",
        project_dir=Path("/nonexistent"),
        user_dir=Path("/nonexistent"),
    )


class TestPromptOnlyFullCycle:
    """Walk the slice pipeline from init through all 6 steps to completion."""

    def test_full_cycle(self, tmp_path: Path) -> None:
        definition = _load_slice_pipeline()
        state_mgr = StateManager(runs_dir=tmp_path)

        # Resolver that handles all model aliases gracefully
        resolver = ModelResolver(pipeline_model="sonnet")

        params: dict[str, object] = {"slice": "152"}

        # ---- Init run ----
        run_id = state_mgr.init_run(definition.name, params)

        # ---- Walk all 6 steps ----
        step_names: list[str] = []
        for step_index, step in enumerate(definition.steps):
            instructions = render_step_instructions(
                step,
                step_index=step_index,
                total_steps=len(definition.steps),
                params=params,
                resolver=resolver,
                run_id=run_id,
            )

            # Verify JSON round-trip
            raw = instructions.to_json()
            parsed = json.loads(raw)
            assert parsed["run_id"] == run_id
            assert parsed["step_index"] == step_index
            assert parsed["total_steps"] == len(definition.steps)
            assert isinstance(parsed["actions"], list)
            assert len(parsed["actions"]) > 0

            step_names.append(instructions.step_name)

            # Mark step done (with verdict for phase steps that have review)
            verdict = (
                "PASS"
                if instructions.step_type in ("design", "tasks", "implement")
                else None
            )
            state_mgr.record_step_done(
                run_id, instructions.step_name, instructions.step_type, verdict=verdict
            )

        # ---- Verify all steps were visited ----
        assert len(step_names) == 6

        # ---- Verify next step returns None (all done) ----
        next_step = state_mgr.first_unfinished_step(run_id, definition)
        assert next_step is None

        # ---- Verify state file ----
        state = state_mgr.load(run_id)
        assert len(state.completed_steps) == 6

        # Verify step types are in expected order
        step_types = [s.step_type for s in state.completed_steps]
        assert step_types == [
            "design",
            "tasks",
            "compact",
            "implement",
            "compact",
            "devlog",
        ]

    def test_first_step_structure(self, tmp_path: Path) -> None:
        """Verify the first step (design) has the expected action structure."""
        definition = _load_slice_pipeline()
        resolver = ModelResolver(pipeline_model="sonnet")
        params: dict[str, object] = {"slice": "152"}

        instructions = render_step_instructions(
            definition.steps[0],
            step_index=0,
            total_steps=len(definition.steps),
            params=params,
            resolver=resolver,
            run_id="run-test",
        )

        assert instructions.step_name == "design-0"
        assert instructions.step_type == "design"

        types = [a.action_type for a in instructions.actions]
        assert types == [
            "cf-op",
            "cf-op",
            "cf-op",
            "dispatch",
            "review",
            "checkpoint",
            "commit",
        ]

        # CF ops
        assert instructions.actions[0].command == "cf set phase 4"
        assert instructions.actions[1].command == "cf set slice 152"
        assert instructions.actions[2].command == "cf build"

        # Dispatch should reference opus
        dispatch = instructions.actions[3]
        assert dispatch.model_switch is not None
        assert "opus" in dispatch.model_switch

        # Review should reference slice template
        review = instructions.actions[4]
        assert review.template == "slice"
        assert "--template" not in review.command
        assert "sq review slice" in review.command

        # Checkpoint
        assert instructions.actions[5].trigger == "on-concerns"

    def test_compact_step_resolves_params(self, tmp_path: Path) -> None:
        """Verify compact step has resolved instructions with slice number."""
        definition = _load_slice_pipeline()
        resolver = ModelResolver(pipeline_model="sonnet")
        params: dict[str, object] = {"slice": "152"}

        # compact is step index 2
        compact_step = definition.steps[2]
        assert compact_step.step_type == "compact"

        instructions = render_step_instructions(
            compact_step,
            step_index=2,
            total_steps=6,
            params=params,
            resolver=resolver,
            run_id="run-test",
        )

        assert len(instructions.actions) == 1
        compact = instructions.actions[0]
        # Slice 169: compact step now renders as a dedicated compact action
        assert compact.action_type == "compact"
        assert compact.trigger == "/compact"

    def test_completion_result_json(self) -> None:
        """Verify CompletionResult serializes as expected."""
        result = CompletionResult(
            status="completed",
            message="All steps complete",
            run_id="run-123",
        )
        parsed = json.loads(result.to_json())
        assert parsed["status"] == "completed"
        assert parsed["run_id"] == "run-123"
