"""Review action — runs a structured review within a pipeline step."""

from __future__ import annotations

import logging

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.review.persistence import (
    CfClientProtocol,
    SliceInfo,
    format_review_markdown,
    resolve_slice_info,
    save_review_file,
    save_review_result,
)
from squadron.review.review_client import run_review_with_profile
from squadron.review.rules import (
    extract_diff_paths,
    load_review_rules,
    resolve_rules_dir,
)
from squadron.review.template_inputs import resolve_template_inputs
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

_INPUT_PASSTHROUGH_KEYS = (
    "diff",
    "diff_exclude_patterns",
    "files",
    "against",
    "input",
)


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
        # cwd comes from ActionContext.cwd, not from config
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
        cwd = context.cwd
        inputs: dict[str, str] = {"cwd": cwd}
        for key in _INPUT_PASSTHROUGH_KEYS:
            if key in context.params:
                inputs[key] = str(context.params[key])

        # Auto-resolve template inputs from slice number when not explicit.
        # Mirrors CLI behavior: `sq review slice 154` resolves input/against
        # automatically — pipelines should do the same.
        slice_param = context.params.get("slice")
        slice_info: SliceInfo | None = None
        if slice_param is not None and "input" not in inputs:
            slice_info = self._resolve_slice_inputs(
                template_name, int(str(slice_param)), context.cf_client, inputs
            )

        # Check required inputs are satisfied after auto-resolution
        missing = [
            inp.name for inp in template.required_inputs if inp.name not in inputs
        ]
        if missing:
            names = ", ".join(missing)
            raise KeyError(
                f"Review template '{template_name}' missing required "
                f"input(s): {names}. The prior step may not have "
                f"created the expected file."
            )

        # Rules content — mirror CLI: template rules + language auto-detection,
        # layered on any explicit rules_content passed in via params.
        manual_rules = (
            str(context.params["rules_content"])
            if "rules_content" in context.params
            else None
        )
        rules_dir = resolve_rules_dir(cwd, None, None)
        file_paths: list[str] = []
        if rules_dir is not None:
            diff_ref = inputs.get("diff")
            if diff_ref:
                exclude_raw = inputs.get("diff_exclude_patterns")
                exclude_patterns = (
                    [p.strip() for p in exclude_raw.split(",") if p.strip()]
                    if exclude_raw
                    else None
                )
                file_paths = extract_diff_paths(diff_ref, cwd, exclude_patterns)
            if not file_paths and inputs.get("files"):
                import glob as _glob

                file_paths = _glob.glob(inputs["files"], root_dir=cwd)
        rules_content = load_review_rules(
            template_name,
            rules_dir,
            file_paths=file_paths,
            manual_rules_content=manual_rules,
        )

        # Execute review
        result = await run_review_with_profile(
            template,
            inputs,
            profile=profile_name,
            model=model_id,
            rules_content=rules_content,
        )

        # File persistence (non-fatal).
        # When slice_info is available, use save_review_result for correct
        # naming (e.g. 154-review.slice.prompt-only-loops.md). Otherwise
        # fall back to save_review_file with step name/index.
        review_file_path: str | None = None
        try:
            if slice_info is not None:
                review_file_path = str(
                    save_review_result(
                        result,
                        template_name,
                        slice_info,
                        input_file=inputs.get("input"),
                    )
                )
            else:
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

    def _resolve_slice_inputs(
        self,
        template_name: str,
        slice_index: int,
        cf_client: CfClientProtocol,
        inputs: dict[str, str],
    ) -> SliceInfo | None:
        """Auto-resolve review inputs from slice number via CF.

        Delegates to ``resolve_template_inputs`` using the declarative registry.
        Returns the resolved SliceInfo for use in file persistence naming.
        """
        try:
            info = resolve_slice_info(cf_client, slice_index)
        except (ValueError, TypeError) as exc:
            _logger.warning("review: could not resolve slice %d: %s", slice_index, exc)
            return None

        resolve_template_inputs(template_name, info, inputs.get("cwd", ""), inputs)
        return info


register_action(ActionType.REVIEW, ReviewAction())
