"""Review action — runs a structured review within a pipeline step."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.actions.judge import Provenance, enforce_judge, resolve_thresholds
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.actions.tool_support import resolve_allowed_tools
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.resolver import (
    ModelPoolNotImplemented,
    ModelResolutionError,
    ResolvedModel,
)
from squadron.providers.base import ProfileName
from squadron.providers.errors import ProviderError
from squadron.review.git_utils import (
    DiffRangeUnresolvedError,
    DiffSpecError,
    EmptyScopeError,
    assert_reviewable_scope,
    normalize_diff_spec,
)
from squadron.review.models import ReviewResult
from squadron.review.persistence import (
    REVIEWS_DIR,
    CfClientProtocol,
    SliceInfo,
    resolve_reviewed_sha,
    resolve_slice_info,
    save_provider_failure,
    save_review_result,
)
from squadron.review.review_client import run_review_with_profile
from squadron.review.rules import (
    RulesSource,
    extract_diff_paths,
    load_review_rules,
    resolve_rules_dir,
)
from squadron.review.save_target import StepTarget
from squadron.review.template_inputs import (
    missing_input_files,
    resolve_template_input_parts,
)
from squadron.review.templates import ReviewTemplate, get_template, load_all_templates

_logger = logging.getLogger(__name__)

_INPUT_PASSTHROUGH_KEYS = (
    "diff",
    "diff_exclude_patterns",
    "files",
    "against",
    "input",
)


def _save_failure_artifact(
    exc: ProviderError,
    template_name: str,
    slice_info: SliceInfo | None,
    *,
    model: str | None,
    source_document: str | None,
    tools_given: list[str] | None,
    cwd: str,
    step_name: str,
    step_index: int,
    run_id: str,
    name_suffix: str | None = None,
) -> Path | None:
    """Resolve the sha and write the failure artifact — all blocking work.

    Kept as one synchronous callable so the caller hands the whole unit to
    ``asyncio.to_thread`` rather than straddling the boundary: resolving the
    sha on the loop and only the write off it would leave the 30-second git
    subprocess exactly where it must not be.
    """
    return save_provider_failure(
        exc,
        template_name,
        slice_info,
        model=model,
        source_document=source_document,
        tools_given=tools_given,
        reviewed_sha=resolve_reviewed_sha(cwd),
        cwd=cwd,
        slice_name=step_name,
        slice_index=step_index,
        run_id=run_id,
        name_suffix=name_suffix,
    )


@dataclass(frozen=True)
class _PartSettings:
    """What every part of one review shares: template, model, rules, target."""

    template: ReviewTemplate
    template_name: str
    resolved: ResolvedModel
    profile_name: str
    rules_content: str | None
    rules_source: RulesSource
    allowed_tools: list[str] | None
    slice_info: SliceInfo | None


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
        except (
            ModelResolutionError,
            ModelPoolNotImplemented,
            KeyError,
            DiffRangeUnresolvedError,
            DiffSpecError,
            EmptyScopeError,
        ) as exc:
            _logger.warning(
                "review: step %s failed before/during template resolution: %s",
                context.step_name,
                exc,
            )
            return self._exception_result(context, exc)
        except Exception as exc:
            _logger.exception("review: unexpected error in step %s", context.step_name)
            return self._exception_result(context, exc)

    def _exception_result(self, context: ActionContext, exc: Exception) -> ActionResult:
        """Build the ActionResult for an exception from _review().

        Best-effort template re-lookup detects whether this was a judge
        template so the failure surfaces as verdict=UNKNOWN/provenance=judge
        (never silently passing a checkpoint). If the template can't be
        found (e.g. the KeyError was the template lookup itself failing),
        falls back to the pre-301 verdict=None/provenance=None shape.
        """
        template_name = context.params.get("template")
        template: ReviewTemplate | None = (
            get_template(str(template_name)) if template_name is not None else None
        )
        is_judge = template is not None and template.is_judge
        return ActionResult(
            success=False,
            action_type=self.action_type,
            outputs={},
            error=str(exc),
            verdict="UNKNOWN" if is_judge else None,
            provenance=Provenance.JUDGE if is_judge else None,
        )

    async def _review(self, context: ActionContext) -> ActionResult:
        template_name = str(context.params["template"])
        template = self._load_template(template_name)
        resolved = self._resolve_model(context, template)

        # Profile resolution — explicit param → alias-derived → SDK default
        profile_name = (
            str(context.params["profile"])
            if "profile" in context.params
            else resolved.profile or ProfileName.SDK
        )

        inputs = self._base_inputs(context)

        # Auto-resolve template inputs from slice number when not explicit.
        # Mirrors CLI behavior: `sq review slice 154` resolves input/against
        # automatically — pipelines should do the same.
        slice_param = context.params.get("slice")
        slice_info: SliceInfo | None = None
        if slice_param is not None and "input" not in inputs:
            slice_info = self._resolve_slice_inputs(
                template_name, int(str(slice_param)), context.cf_client, inputs
            )

        self._validate_inputs(template, template_name, inputs)
        rules_content, rules_source = self._resolve_rules(context, template_name, inputs)

        # A step-level allowed_tools overrides the template's default; None leaves the
        # template authoritative (slice 265).
        allowed_tools = resolve_allowed_tools(context, self.action_type)
        settings = _PartSettings(
            template=template,
            template_name=template_name,
            resolved=resolved,
            profile_name=profile_name,
            rules_content=rules_content,
            rules_source=rules_source,
            allowed_tools=allowed_tools,
            slice_info=slice_info,
        )
        return await self._run_part(settings, context, inputs)

    def _load_template(self, template_name: str) -> ReviewTemplate:
        load_all_templates()
        template = get_template(template_name)
        if template is None:
            raise KeyError(f"Review template '{template_name}' not found")
        return template

    def _resolve_model(self, context: ActionContext, template: ReviewTemplate) -> ResolvedModel:
        # Model resolution — same pattern as dispatch, with one addition: when
        # the standard cascade (CLI/action/step/pipeline/config) is entirely
        # empty, fall back to the template's own `model:` default — the same
        # fallback `sq review` already applies via its CLI-side cascade
        # (cli/commands/review.py:_resolve_model). Without this, a judge
        # template's declared default model is silently unreachable from any
        # pipeline `review:` step.
        action_model = str(context.params["model"]) if "model" in context.params else None
        step_model = str(context.params["step_model"]) if "step_model" in context.params else None
        # resolve_full, not resolve: the alias's tool_use gate and output budget can
        # only be read while its name is known (slice 924 D6).
        try:
            return context.resolver.resolve_full(action_model, step_model)
        except ModelResolutionError:
            if template.model is None:
                raise
            return context.resolver.resolve_full(template.model, step_model)

    def _base_inputs(self, context: ActionContext) -> dict[str, str]:
        cwd = context.cwd
        inputs: dict[str, str] = {"cwd": cwd}
        for key in _INPUT_PASSTHROUGH_KEYS:
            if key in context.params:
                inputs[key] = str(context.params[key])

        # A step-supplied bare ref needs merge-base semantics exactly as the
        # CLI's --diff does (issue #89). Interface parity is the point: `sq run`
        # is the less-watched entry point, so a range bug here is the harder one
        # to notice. Slice-derived ranges are resolved below and arrive explicit,
        # so only the step-supplied value passes through here.
        if inputs.get("diff"):
            inputs["diff"] = normalize_diff_spec(inputs["diff"], cwd)
        return inputs

    def _validate_inputs(
        self, template: ReviewTemplate, template_name: str, inputs: dict[str, str]
    ) -> None:
        # Check required inputs are satisfied after auto-resolution
        missing = [inp.name for inp in template.required_inputs if inp.name not in inputs]
        if missing:
            names = ", ".join(missing)
            raise KeyError(
                f"Review template '{template_name}' missing required "
                f"input(s): {names}. The prior step may not have "
                f"created the expected file."
            )

        # input/against must name real files — a stale path would otherwise
        # reach the model with its content silently absent, and the model
        # reviews a document it never saw (issue #18).
        not_found = missing_input_files(inputs)
        if not_found:
            details = ", ".join(f"{key}={value}" for key, value in not_found)
            raise KeyError(
                f"Review template '{template_name}' input file(s) not "
                f"found: {details}. The prior step may not have created "
                f"the expected file."
            )

    def _resolve_rules(
        self, context: ActionContext, template_name: str, inputs: dict[str, str]
    ) -> tuple[str | None, RulesSource]:
        # Rules content — mirror CLI: template rules + language auto-detection,
        # layered on any explicit rules_content passed in via params.
        cwd = context.cwd
        manual_rules = (
            str(context.params["rules_content"]) if "rules_content" in context.params else None
        )
        diff_ref = inputs.get("diff")
        exclude_raw = inputs.get("diff_exclude_patterns")
        exclude_patterns = (
            [p.strip() for p in exclude_raw.split(",") if p.strip()] if exclude_raw else None
        )

        # Pre-flight: refuse a range with nothing reviewable in it before the
        # model is called. `sq run` is the path that clears review gates, so a
        # review of nothing passing here is the harm this guard exists to stop
        # (issue #62). Outside the rules-dir branch by design — a review with no
        # rules directory needs the guard just as much.
        if diff_ref:
            assert_reviewable_scope(diff_ref, cwd, exclude_patterns)

        rules_dir, rules_source = resolve_rules_dir(cwd, None, None)
        file_paths: list[str] = []
        if rules_dir is not None:
            if diff_ref:
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
        return rules_content, rules_source

    async def _run_part(
        self,
        settings: _PartSettings,
        context: ActionContext,
        inputs: dict[str, str],
        name_suffix: str | None = None,
    ) -> ActionResult:
        """Review one part: model call, judge enforcement, save, result."""
        try:
            result = await run_review_with_profile(
                settings.template,
                inputs,
                profile=settings.profile_name,
                model=settings.resolved.model_id,
                rules_content=settings.rules_content,
                allowed_tools=settings.allowed_tools,
                model_allows_tools=settings.resolved.allows_tools,
                max_output_tokens=settings.resolved.max_output_tokens,
            )
        except ProviderError as exc:
            # For a pipeline run the artifact is the whole durable record, so a
            # provider failure that leaves nothing on disk erases the only
            # evidence of why the step failed (#84). The step still fails: the
            # re-raise reaches execute's catch-all, which builds the existing
            # success=False result.
            # Off-thread: the save runs a git subprocess bounded at 30s plus
            # file I/O, and no blocking call belongs on the event loop inside
            # an async def (project async rule; the frontmatter gate states the
            # same convention).
            saved = await asyncio.to_thread(
                _save_failure_artifact,
                exc,
                settings.template_name,
                settings.slice_info,
                model=settings.resolved.model_id,
                source_document=inputs.get("input"),
                tools_given=list(settings.allowed_tools) if settings.allowed_tools else None,
                cwd=context.cwd,
                step_name=context.step_name,
                step_index=context.step_index,
                run_id=context.run_id,
                name_suffix=name_suffix,
            )
            _logger.warning(
                "review: provider failed in step %s; failure artifact: %s",
                context.step_name,
                saved if saved is not None else "not written",
            )
            raise

        # Traceability (slice 195 D12, #139): the run that wrote this review.
        result.run_id = context.run_id
        verdict, provenance, verdict_override = self._enforce_verdict(settings, context, result)
        review_file_path = await self._save_part(
            settings, context, result, inputs, verdict_override, name_suffix
        )
        return self._part_result(settings, result, inputs, review_file_path, verdict, provenance)

    def _enforce_verdict(
        self, settings: _PartSettings, context: ActionContext, result: ReviewResult
    ) -> tuple[str, str, str | None]:
        """Return (verdict, provenance, verdict_override for persistence).

        Judge enforcement runs before persistence: judge templates instruct
        the model to omit a verdict line (score is the source of truth), so
        result.verdict is always UNKNOWN for them. The persisted file must
        show the threshold-derived verdict instead, not the always-empty
        raw parse.

        Threshold resolution/enforcement must not discard an already-
        successful model call: a malformed threshold override (e.g. a
        non-numeric pass_floor) degrades to UNKNOWN with a WARNING rather
        than raising here, so persistence still runs and the review
        artifact is saved (slice 303 F003).
        """
        template_name = settings.template_name
        if not settings.template.is_judge:
            return result.verdict.value, Provenance.REVIEW, None
        judge_override = context.params.get("judge")
        step_override = (
            cast(dict[str, object], judge_override) if isinstance(judge_override, dict) else None
        )
        try:
            thresholds = resolve_thresholds(settings.template.judge, step_override)
            verdict, provenance = enforce_judge(result, thresholds, template_name, _logger)
        except (TypeError, ValueError):
            _logger.warning(
                "review: malformed judge threshold override for template '%s'; verdict=UNKNOWN",
                template_name,
            )
            verdict, provenance = "UNKNOWN", Provenance.JUDGE
        return verdict, provenance, verdict

    async def _save_part(
        self,
        settings: _PartSettings,
        context: ActionContext,
        result: ReviewResult,
        inputs: dict[str, str],
        verdict_override: str | None,
        name_suffix: str | None,
    ) -> str | None:
        """Persist one part's review artifact; ``None`` when the save failed.

        When slice_info is available, use save_review_result for correct
        naming (e.g. 154-review.slice.prompt-only-loops.md). Otherwise
        fall back to the step name/index target.
        """
        cwd = context.cwd
        # revision_number (slice 911 Part B): the loop iteration this review
        # ran in, supplied only when it actually ran inside a loop.
        revision_number = context.iteration if context.iteration >= 1 else None
        try:
            # Off-thread for the same reason the provider-failure branch is:
            # the save runs a git subprocess bounded at 30s through the
            # target's reviewed_sha(), plus archive_existing_review's read and
            # write, and no blocking call belongs on the event loop inside an
            # async def (project async rule).
            if settings.slice_info is not None:
                return str(
                    await asyncio.to_thread(
                        save_review_result,
                        result,
                        settings.template_name,
                        settings.slice_info,
                        input_file=inputs.get("input"),
                        name_suffix=name_suffix,
                        verdict_override=verdict_override,
                        revision_number=revision_number,
                    )
                )
            # Through the contract rather than format + save_review_file
            # directly (slice 383, D2). This is the one save path that
            # never ran archive_existing_review's guard, so it could
            # overwrite a review whose prior content could not be
            # preserved; routing it here closes that gap. The refusal
            # arrives as OSError where the old call returned None, and the
            # boundary below keeps it non-fatal to the action exactly as
            # a write failure was.
            return str(
                await asyncio.to_thread(
                    save_review_result,
                    result,
                    settings.template_name,
                    reviews_dir=Path(cwd) / REVIEWS_DIR,
                    input_file=inputs.get("input"),
                    name_suffix=name_suffix,
                    verdict_override=verdict_override,
                    revision_number=revision_number,
                    target=StepTarget(
                        context.step_name,
                        context.step_index,
                        cwd=cwd,
                        rules_source=settings.rules_source,
                    ),
                )
            )
        except Exception:  # noqa: BLE001
            # Boundary by design: this block only persists the review markdown
            # artifact (file write + templating + a git-sha subprocess call);
            # the review itself already succeeded and its result is returned
            # regardless. A failure to save the secondary artifact must
            # not fail the action's primary output, the review response.
            _logger.exception(
                "review: failed to persist review file for step %s",
                context.step_name,
            )
            return None

    def _part_result(
        self,
        settings: _PartSettings,
        result: ReviewResult,
        inputs: dict[str, str],
        review_file_path: str | None,
        verdict: str,
        provenance: str,
    ) -> ActionResult:
        """Map one part's ReviewResult → ActionResult."""
        outputs: dict[str, object] = {ReviewOutputKey.RESPONSE: result.raw_output}
        if review_file_path is not None:
            outputs[ReviewOutputKey.REVIEW_FILE] = review_file_path
        # What was reviewed, so a `feedback: review` dispatch can name the file
        # to revise in place (slice 195 D8).
        if "input" in inputs:
            outputs[ReviewOutputKey.INPUT_FILE] = inputs["input"]

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs=outputs,
            verdict=verdict,
            findings=[sf.__dict__ for sf in result.structured_findings],
            # Numeric scoring foundation (slice 300): pass through score/criteria.
            score=result.score,
            criteria=result.criteria,
            provenance=provenance,
            metadata={
                # Slice 927 D10: the model that answered, not the one requested — the
                # same distinction the artifact's aiModel/requestedModel pair makes.
                "model": result.model,
                "requested_model": settings.resolved.model_id,
                "profile": settings.profile_name,
                "template": settings.template_name,
                # Absent when the review ran without tools, so a zero count always means
                # "offered and declined" rather than "never offered" (design D5).
                **(
                    {
                        "tools_given": result.tools_given,
                        "tool_calls_made": result.tool_calls_made or 0,
                    }
                    if result.tools_given
                    else {}
                ),
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

        Delegates to ``resolve_template_input_parts`` using the declarative registry.
        Returns the resolved SliceInfo for use in file persistence naming.
        """
        try:
            info = resolve_slice_info(cf_client, slice_index)
        except (ValueError, TypeError) as exc:
            _logger.warning("review: could not resolve slice %d: %s", slice_index, exc)
            return None

        # TEMPORARY (slice 930 Task 4): only the first part is reviewed until the
        # part loop lands in Task 7a, which replaces this shim.
        parts = resolve_template_input_parts(template_name, info, inputs.get("cwd", ""), inputs)
        inputs.update(parts[0])
        return info


register_action(ActionType.REVIEW, ReviewAction())
