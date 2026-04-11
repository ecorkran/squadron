"""Compact action — issues compaction instructions to ContextForge."""

from __future__ import annotations

from typing import cast

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.compaction_templates import (
    CompactionTemplate,
    _parse_template,
    load_compaction_template,
    render_instructions,
)
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

__all__ = [
    "CompactionTemplate",
    "_parse_template",
    "load_compaction_template",
    "render_instructions",
    "CompactAction",
]


class CompactAction:
    """Pipeline action that issues compaction instructions to ContextForge."""

    @property
    def action_type(self) -> str:
        return ActionType.COMPACT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []

        keep = config.get("keep")
        if keep is not None and (
            not isinstance(keep, list)
            or not all(isinstance(item, str) for item in cast(list[object], keep))
        ):
            errors.append(
                ValidationError(
                    field="keep",
                    message="'keep' must be a list of strings",
                    action_type=self.action_type,
                )
            )

        summarize = config.get("summarize")
        if summarize is not None and not isinstance(summarize, bool):
            errors.append(
                ValidationError(
                    field="summarize",
                    message="'summarize' must be a boolean",
                    action_type=self.action_type,
                )
            )

        template = config.get("template")
        if template is not None and not isinstance(template, str):
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' must be a string",
                    action_type=self.action_type,
                )
            )

        model = config.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.action_type,
                )
            )

        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        template_name = str(context.params.get("template", "default"))
        keep_raw = context.params.get("keep")
        keep: list[str] | None = (
            [str(item) for item in cast(list[object], keep_raw)]
            if isinstance(keep_raw, list)
            else None
        )
        summarize = bool(context.params.get("summarize", False))

        try:
            template = load_compaction_template(template_name)
        except FileNotFoundError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        instructions = render_instructions(
            template,
            keep=keep,
            summarize=summarize,
            pipeline_params=context.params,
        )

        # SDK mode: delegate into the shared summary helper, which captures
        # the summary once and emits to rotate.  action_type stays "compact" so
        # StateManager._maybe_record_compact_summaries() continues to fire.
        if context.sdk_session is not None:
            from squadron.pipeline.actions.summary import (
                _execute_summary,  # pyright: ignore[reportPrivateUsage]
            )
            from squadron.pipeline.emit import EmitDestination, EmitKind

            model_raw = context.params.get("model")
            summary_model_alias = model_raw if isinstance(model_raw, str) else None

            return await _execute_summary(
                context=context,
                instructions=instructions,
                summary_model_alias=summary_model_alias,
                emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
                action_type=self.action_type,  # stays "compact"
            )

        cf_client: ContextForgeClient = context.cf_client  # type: ignore[assignment]

        try:
            stdout = cf_client._run(  # pyright: ignore[reportPrivateUsage]
                ["compact", "--instructions", instructions]
            )

            summarize_stdout = ""
            if summarize:
                summarize_stdout = cf_client._run(  # pyright: ignore[reportPrivateUsage]
                    ["summarize"]
                )
        except ContextForgeError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        outputs: dict[str, object] = {
            "stdout": stdout,
            "instructions": instructions,
        }
        if summarize:
            outputs["summarize_stdout"] = summarize_stdout

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs=outputs,
        )


register_action(ActionType.COMPACT, CompactAction())
