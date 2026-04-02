"""Review action — runs a structured review within a pipeline step."""

from __future__ import annotations

import logging

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.review.persistence import (
    format_review_markdown,
    save_review_file,
)
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

_INPUT_PASSTHROUGH_KEYS = ("diff", "files", "against", "input")


class ReviewAction:
    """Pipeline action that delegates to the review subsystem.

    Resolves template, model, and profile from ``context.params``,
    executes the review, persists the output file, and maps the
    ``ReviewResult`` to an ``ActionResult`` with verdict and findings.
    """

    @property
    def action_type(self) -> str:
        return ActionType.REVIEW

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if "template" not in config:
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' is required for review action",
                    action_type=ActionType.REVIEW,
                )
            )
        if "cwd" not in config:
            errors.append(
                ValidationError(
                    field="cwd",
                    message="'cwd' is required for review action",
                    action_type=ActionType.REVIEW,
                )
            )
        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        try:
            return await self._review(context)
        except (ModelResolutionError, ModelPoolNotImplemented, KeyError) as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )
        except Exception as exc:
            _logger.exception("review: unexpected error in step %s", context.step_name)
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

    async def _review(self, context: ActionContext) -> ActionResult:
        # Template resolution
        load_all_templates()
        template_name = str(context.params["template"])
        template = get_template(template_name)
        if template is None:
            raise KeyError(f"Review template '{template_name}' not found")

        # Model resolution — same pattern as dispatch
        action_model = (
            str(context.params["model"]) if "model" in context.params else None
        )
        step_model = (
            str(context.params["step_model"])
            if "step_model" in context.params
            else None
        )
        model_id, alias_profile = context.resolver.resolve(action_model, step_model)

        # Profile resolution — explicit param → alias-derived → SDK default
        profile_name = (
            str(context.params["profile"])
            if "profile" in context.params
            else alias_profile or ProfileName.SDK
        )

        # Build review inputs
        cwd = str(context.params["cwd"])
        inputs: dict[str, str] = {"cwd": cwd}
        for key in _INPUT_PASSTHROUGH_KEYS:
            if key in context.params:
                inputs[key] = str(context.params[key])

        # Rules content
        rules_content: str | None = None
        if "rules_content" in context.params:
            rules_content = str(context.params["rules_content"])

        # Execute review
        result = await run_review_with_profile(
            template,
            inputs,
            profile=profile_name,
            model=model_id,
            rules_content=rules_content,
        )

        # File persistence (non-fatal)
        review_file_path: str | None = None
        try:
            md_content = format_review_markdown(
                result, template_name, source_document=inputs.get("input")
            )
            path = save_review_file(
                md_content,
                template_name,
                context.step_name,
                context.step_index,
                cwd=cwd,
            )
            if path is not None:
                review_file_path = str(path)
        except Exception:
            _logger.warning(
                "review: failed to persist review file for step %s",
                context.step_name,
            )

        # Map ReviewResult → ActionResult
        outputs: dict[str, object] = {"response": result.raw_output}
        if review_file_path is not None:
            outputs["review_file"] = review_file_path

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs=outputs,
            verdict=result.verdict.value,
            findings=[sf.__dict__ for sf in result.structured_findings],
            metadata={
                "model": model_id,
                "profile": profile_name,
                "template": template_name,
            },
        )


register_action(ActionType.REVIEW, ReviewAction())
