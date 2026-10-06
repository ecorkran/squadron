"""Phase step type — expands a named phase into a sequence of actions."""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.commit_plan import REVIEW_TEMPLATE_PARAM, SUBJECT_PARAM, CommitSubject
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type
from squadron.pipeline.steps.utils import validate_allowed_tools


class ArtifactKind(StrEnum):
    """The kind of artifact a phase step's dispatch is expected to write."""

    DESIGN = "design"
    TASKS = "tasks"


class ExistingArtifactPolicy(StrEnum):
    """What a design or tasks step does when its artifact already exists (slice 196 D11)."""

    CREATE = "create"  # dispatch always writes the artifact (the default)
    KEEP = "keep"  # skip the model call; the step's review still runs


class KeepCheck(StrEnum):
    """What ``existing: keep`` looks for before skipping a step's dispatch."""

    ARTIFACT = "artifact"  # the design or tasks file is on disk (196 D11)
    BRANCH_WORK = "branch_work"  # the slice branch has commits ahead of the target (197 D4)


# Dispatch config keys that carry the policy, its check and the artifact kind to the
# dispatch action.
EXISTING_PARAM = "existing"
KEEP_CHECK_PARAM = "keep_check"
ARTIFACT_KIND_PARAM = "artifact_kind"

_KEEP_CHECK: dict[str, KeepCheck] = {
    StepTypeName.DESIGN: KeepCheck.ARTIFACT,
    StepTypeName.TASKS: KeepCheck.ARTIFACT,
    StepTypeName.IMPLEMENT: KeepCheck.BRANCH_WORK,
}

_EXPECTED_ARTIFACT_KIND: dict[str, ArtifactKind | None] = {
    StepTypeName.DESIGN: ArtifactKind.DESIGN,
    StepTypeName.TASKS: ArtifactKind.TASKS,
    StepTypeName.IMPLEMENT: None,
}


# What each phase's own commit is about. An initiative-scoped step (a plan and no
# slice) edits the architecture document whatever its phase name is.
_COMMIT_SUBJECT: dict[str, CommitSubject] = {
    StepTypeName.DESIGN: CommitSubject.DESIGN,
    StepTypeName.TASKS: CommitSubject.TASKS,
    StepTypeName.IMPLEMENT: CommitSubject.CODE,
}


class PhaseStepType:
    """Step type for design, tasks, and implement phases.

    Expands to: [cf-op(set_arch)] -> cf-op(set_slice) -> cf-op(set_phase)
    -> cf-op(build) -> dispatch -> [review -> checkpoint] -> commit.
    set_arch is included only when ``plan:`` is set; review and checkpoint
    only when review is configured.
    """

    def __init__(self, phase_name: str) -> None:
        self._phase_name = phase_name

    @property
    def step_type(self) -> str:
        return self._phase_name

    @property
    def expected_artifact_kind(self) -> ArtifactKind | None:
        """The artifact kind this phase's dispatch is expected to write.

        ``None`` means the phase has no single deterministic artifact (e.g.
        ``implement``, which mutates arbitrary source) — the dispatch
        artifact post-condition does not apply.
        """
        return _EXPECTED_ARTIFACT_KIND.get(self._phase_name)

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        phase = cfg.get("phase")
        if phase is None:
            errors.append(
                ValidationError(
                    field="phase",
                    message="'phase' is required",
                    action_type=self._phase_name,
                )
            )
        elif not isinstance(phase, int):
            errors.append(
                ValidationError(
                    field="phase",
                    message="'phase' must be an integer",
                    action_type=self._phase_name,
                )
            )

        review = cfg.get("review")
        if review is not None:
            if isinstance(review, dict):
                if "template" not in cast(dict[str, object], review):
                    errors.append(
                        ValidationError(
                            field="review",
                            message="review dict must contain 'template' key",
                            action_type=self._phase_name,
                        )
                    )
            elif not isinstance(review, str):
                errors.append(
                    ValidationError(
                        field="review",
                        message="'review' must be a string or dict with 'template' key",
                        action_type=self._phase_name,
                    )
                )

        checkpoint = cfg.get("checkpoint")
        if checkpoint is not None:
            valid_triggers = [t.value for t in CheckpointTrigger]
            if checkpoint not in valid_triggers:
                errors.append(
                    ValidationError(
                        field="checkpoint",
                        message=(
                            f"'{checkpoint}' is not a valid checkpoint trigger. "
                            f"Valid values: {valid_triggers}"
                        ),
                        action_type=self._phase_name,
                    )
                )

        model = cfg.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self._phase_name,
                )
            )

        plan = cfg.get("plan")
        if plan is not None and not isinstance(plan, str | int):
            errors.append(
                ValidationError(
                    field="plan",
                    message="'plan' must be an architecture index",
                    action_type=self._phase_name,
                )
            )

        fragment = cfg.get("pre_emption_fragment")
        if fragment is not None and not isinstance(fragment, str):
            errors.append(
                ValidationError(
                    field="pre_emption_fragment",
                    message="'pre_emption_fragment' must be a string",
                    action_type=self._phase_name,
                )
            )

        errors.extend(self._validate_existing(config))
        errors.extend(validate_allowed_tools(config, self._phase_name))

        return errors

    def _validate_existing(self, config: StepConfig) -> list[ValidationError]:
        """``existing:`` must name a policy, and ``keep`` needs a slice-scoped phase step."""
        cfg = config.config
        raw = cfg.get(EXISTING_PARAM)
        if raw is None:
            return []
        valid = [p.value for p in ExistingArtifactPolicy]
        if raw not in valid:
            return [self._existing_error(f"'{raw}' is not a valid 'existing' policy; one of {valid}")]
        initiative_scoped = "plan" in cfg and "slice" not in cfg
        if raw == ExistingArtifactPolicy.KEEP and (
            self._phase_name not in _KEEP_CHECK or initiative_scoped
        ):
            return [
                self._existing_error(
                    "'existing: keep' applies to a slice's design, tasks or implement step, "
                    "which has an artifact or branch work to keep"
                )
            ]
        return []

    def _existing_error(self, message: str) -> ValidationError:
        return ValidationError(field=EXISTING_PARAM, message=message, action_type=self._phase_name)

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        phase = cfg["phase"]
        model = cfg.get("model")
        # Step config may set its own "slice" placeholder (e.g. "{slice.index}"
        # inside an each-loop, where the loop's "as" variable binds a whole
        # record rather than a scalar index). Prefer it over the bare
        # "{slice}" default so per-action placeholder resolution reaches the
        # loop item's .index field instead of stringifying the whole record.
        # A step with a plan and no slice is initiative-scoped (e.g. phase 2,
        # architecture): there is no slice to set, and its review covers the
        # initiative's architecture document.
        initiative_scoped = "plan" in cfg and "slice" not in cfg
        slice_ref = None if initiative_scoped else cfg.get("slice", "{slice}")
        target: dict[str, object] = {"plan": cfg["plan"]} if initiative_scoped else {"slice": slice_ref}

        dispatch_config: dict[str, object] = {"model": model, **target}
        # Conditional, not unconditional: an absent key must leave the
        # expanded dict byte-identical to its pre-324 shape, which the
        # existing exact-equality expand() tests assert.
        if "pre_emption_fragment" in cfg:
            dispatch_config["pre_emption_fragment"] = cfg["pre_emption_fragment"]
        # Only a ``keep`` policy travels to dispatch, so the default shape is unchanged.
        if cfg.get(EXISTING_PARAM) == ExistingArtifactPolicy.KEEP:
            dispatch_config[EXISTING_PARAM] = ExistingArtifactPolicy.KEEP
            if self.expected_artifact_kind is not None:
                dispatch_config[ARTIFACT_KIND_PARAM] = self.expected_artifact_kind
            else:
                dispatch_config[KEEP_CHECK_PARAM] = _KEEP_CHECK[self._phase_name]
        # Tools go only to the dispatch action; the review path is slice 265.
        if "allowed_tools" in cfg:
            dispatch_config["allowed_tools"] = cfg["allowed_tools"]

        # cf's switching rule (slice 195 D2): arch (switches initiative and
        # plan) → slice (must be in that plan) → phase → build.
        actions: list[tuple[str, dict[str, object]]] = [
            ("cf-op", {"operation": "set_phase", "phase": phase}),
            ("cf-op", {"operation": "build_context"}),
            ("dispatch", dispatch_config),
        ]
        if not initiative_scoped:
            actions.insert(0, ("cf-op", {"operation": "set_slice", "slice": slice_ref}))
        if "plan" in cfg:
            actions.insert(0, ("cf-op", {"operation": "set_arch", "plan": cfg["plan"]}))

        review = cfg.get("review")
        if review is not None:
            if isinstance(review, str):
                actions.append(("review", {"template": review, "model": None, **target}))
            elif isinstance(review, dict):
                review_dict = cast(dict[str, object], review)
                actions.append(
                    (
                        "review",
                        {
                            "template": review_dict["template"],
                            "model": review_dict.get("model"),
                            **target,
                        },
                    )
                )

            checkpoint = cfg.get("checkpoint", CheckpointTrigger.NEVER)
            actions.append(("checkpoint", {"trigger": checkpoint}))

        subject = CommitSubject.ARCHITECTURE if initiative_scoped else _COMMIT_SUBJECT[self._phase_name]
        commit_config: dict[str, object] = {SUBJECT_PARAM: subject, **target}
        # The step's own review (if any) is what its commit reports a verdict for.
        review_template = _review_template(cfg.get("review"))
        if review_template is not None:
            commit_config[REVIEW_TEMPLATE_PARAM] = review_template
        actions.append(("commit", commit_config))

        return actions


def _review_template(review: object) -> str | None:
    """The template named by a phase step's ``review:`` (a string, or a dict with ``template``)."""
    if isinstance(review, str):
        return review
    if isinstance(review, dict):
        template = cast(dict[str, object], review).get("template")
        return str(template) if template is not None else None
    return None


register_step_type(StepTypeName.DESIGN, PhaseStepType("design"))
register_step_type(StepTypeName.TASKS, PhaseStepType("tasks"))
register_step_type(StepTypeName.IMPLEMENT, PhaseStepType("implement"))
