"""``sq review <kind> --max N``: one review, then revise-and-review rounds (slice 941).

``RoundPrinter`` is the ``RunObserver`` that prints progress as the composed
pipeline runs; ``run_review_revise`` drives that pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import click
import typer
from click.core import ParameterSource

from squadron.integrations.context_forge import ContextForgeClient
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.branch_ops import dirty_paths, slice_facts
from squadron.pipeline.classification import ClassificationError
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult, execute_pipeline
from squadron.pipeline.git_ops import (
    GitEnvironmentError,
    NoDesignFileError,
    SliceNotInPlanError,
    current_branch,
    read_integration_target,
)
from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend
from squadron.pipeline.loop_config import last_with_verdict
from squadron.pipeline.models import ActionResult, PipelineDefinition
from squadron.pipeline.review_revise import REVIEW_STEP_NAME, build_review_revise_definition
from squadron.pipeline.run_lock import RunLockError, pipeline_mutates, project_run_lock
from squadron.pipeline.run_session import classify_for_run, pipeline_session, run_resolver
from squadron.pipeline.state import ActiveItem, StateManager
from squadron.pipeline.steps import StepTypeName
from squadron.review.models import Verdict
from squadron.review.templates import BuiltinReviewTemplate

# The only options `--max` honors (D6), by Python parameter name. Any other option given
# on the command line is refused: the loop's review steps cannot honor it, and silently
# ignoring it would be a fallback. Options added to `sq review` later are refused by default.
MAX_SUPPORTED_OPTIONS = frozenset({"max_rounds", "model", "revise_model", "cwd", "verbose"})

_logger = logging.getLogger(__name__)

# The pipeline param the loop's revise dispatch reads its model from (D3).
REVISER_PARAM = "model"

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_REVIEW_FAILED = 2

_SHORT_SHA_LENGTH = 7
_LABEL_WIDTH = 10
_VERDICT_WIDTH = 14


def _single(results: list[ActionResult], action_type: str) -> ActionResult | None:
    return next((r for r in results if r.action_type == action_type), None)


class RoundPrinter:
    """Prints the review line, one line per round, and nothing else (D7).

    Never raises: a ``RunObserver`` must not fail a run through a progress write. The
    builder already guarantees each round has a review and a commit result, so a missing
    one prints a visible placeholder, never a guess.
    """

    def __init__(self, write: Callable[[str], None] = typer.echo) -> None:
        self._write = write

    def header(self, kind: str, slice_index: str, reviewer: str, reviser: str, max_rounds: int) -> None:
        self._write(
            f"review-revise {kind} {slice_index}  reviewer={reviewer}  "
            f"reviser={reviser}  max={max_rounds}"
        )

    def step_started(self, step_name: str) -> None:
        """Nothing to print: lines appear when work finishes."""

    def item_started(self, step_name: str, item: ActiveItem) -> None:
        """No ``each`` step exists in the composed pipeline."""

    def step_completed(self, result: StepResult) -> None:
        """Print the leading review's line; the loop's rounds print via ``round_completed``."""
        if result.step_name != REVIEW_STEP_NAME:
            return
        review = _single(result.action_results, "review")
        file_name = review.outputs.get(ReviewOutputKey.REVIEW_FILE, "") if review else ""
        self._write(f"  {'review':<{_LABEL_WIDTH}}{_verdict_cell(review)}{file_name}".rstrip())

    def round_completed(self, step_name: str, iteration: int, results: list[ActionResult]) -> None:
        label = f"round {iteration}"
        review = _single(results, "review")
        commit = _single(results, "commit")
        self._write(f"  {label:<{_LABEL_WIDTH}}{_verdict_cell(review)}{_commit_text(commit)}".rstrip())


def _verdict_cell(review: ActionResult | None) -> str:
    if review is None:
        text = "<no review result>"
    elif not review.success:
        # A failed review is a run failure, reported here and mapped to exit 1 later.
        return f"review failed: {review.error}  "
    elif review.verdict is None:
        text = "<no verdict>"
    else:
        text = f"{review.verdict} ({len(review.findings)})" if review.findings else review.verdict
    return f"{text:<{_VERDICT_WIDTH}}"


def _commit_text(commit: ActionResult | None) -> str:
    if commit is None:
        return "<no commit result>"
    if not commit.success:
        return "commit failed"
    if commit.outputs.get("committed") is False:
        return "no changes"
    return f"committed {str(commit.outputs.get('sha', '<no sha>'))[:_SHORT_SHA_LENGTH]}"


@dataclass(frozen=True)
class ReviseOutcome:
    """What a finished review-revise run earned (D5)."""

    exit_code: int
    final_verdict: str | None
    rounds: int
    error: str | None = None


def outcome_of(result: PipelineResult) -> ReviseOutcome:
    """Map the composed pipeline's result to the D5 exit code.

    ``accepted`` and ``exhausted`` are read before run status: an exhausted,
    unaccepted loop has FAILED status but exits 2, not 1.
    """
    review = next((r for r in result.step_results if r.step_name == REVIEW_STEP_NAME), None)
    loop = next((r for r in result.step_results if r.step_type == StepTypeName.LOOP), None)
    if review is None or review.status != ExecutionStatus.COMPLETED or loop is None:
        return ReviseOutcome(EXIT_RUN_FAILED, None, 0, _failure_text(result))
    rounds = loop.iteration
    final = last_with_verdict(loop.action_results if rounds > 0 else review.action_results)
    verdict = final.verdict if final is not None else None
    if loop.exhausted and not loop.accepted:
        return ReviseOutcome(EXIT_REVIEW_FAILED, verdict, rounds)
    if loop.status != ExecutionStatus.COMPLETED:
        return ReviseOutcome(EXIT_RUN_FAILED, verdict, rounds, _failure_text(result))
    if verdict == Verdict.FAIL and not loop.accepted:
        return ReviseOutcome(EXIT_REVIEW_FAILED, verdict, rounds)
    # A FAIL keeps precedence (as `_exit_on`), but a passing run must not exit 0 when
    # the review it ends on was never written: reruns and gates read the file.
    if final is None or not _saved(final):
        return ReviseOutcome(EXIT_RUN_FAILED, verdict, rounds, "the final review was not saved")
    return ReviseOutcome(EXIT_OK, verdict, rounds)


def _saved(review: ActionResult) -> bool:
    return (
        ReviewOutputKey.REVIEW_FILE in review.outputs or ReviewOutputKey.REVIEW_FILES in review.outputs
    )


def _failure_text(result: PipelineResult) -> str:
    """The failing step's error as the executor reported it, for stderr."""
    for step in result.step_results:
        if step.status == ExecutionStatus.COMPLETED:
            continue
        if step.error is not None:
            return step.error
        action_error = next((a.error for a in step.action_results if a.error), None)
        return action_error or f"step '{step.step_name}' ended {step.status}"
    return result.error or "pipeline did not finish"


def run_review_revise(
    kind: BuiltinReviewTemplate,
    slice_index: str,
    reviewer: str,
    revise_model: str | None,
    max_rounds: int,
    cwd: str,
) -> int:
    """Run one review and up to *max_rounds* revise-and-review rounds; return the exit code.

    Holds the project run lock, as ``sq run`` does for a mutating pipeline: every round
    commits, so two runs in one checkout would interleave their commits.
    """
    try:
        definition = build_review_revise_definition(kind)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        return EXIT_RUN_FAILED
    with ExitStack() as lock:
        if pipeline_mutates(definition):
            try:
                lock.enter_context(project_run_lock(cwd))
            except (GitEnvironmentError, RunLockError) as exc:
                typer.echo(f"Error: {exc}", err=True)
                return EXIT_RUN_FAILED
        return asyncio.run(_run(definition, kind, slice_index, reviewer, revise_model, max_rounds, cwd))


async def _run(
    definition: PipelineDefinition,
    kind: BuiltinReviewTemplate,
    slice_index: str,
    reviewer: str,
    revise_model: str | None,
    max_rounds: int,
    cwd: str,
) -> int:
    # `model` only when given: otherwise the mapped pipeline's own default applies (D3).
    overrides: dict[str, object] = {
        "slice": slice_index,
        "review-model": reviewer,
        "max-revisions": str(max_rounds),
    }
    if revise_model is not None:
        overrides["model"] = revise_model
    params = {k: v for k, v in definition.params.items() if v != "required"} | overrides
    reviser = params.get(REVISER_PARAM)
    if reviser is None:
        typer.echo(
            f"Error: pipeline {definition.name} has no '{REVISER_PARAM}' param; pass --revise-model",
            err=True,
        )
        return EXIT_RUN_FAILED
    try:
        classification = classify_for_run(definition, model_override=None, params=params, strict=False)
    except ClassificationError as exc:
        typer.echo(f"Error: pipeline classification failed: {exc}", err=True)
        return EXIT_RUN_FAILED

    printer = RoundPrinter()
    printer.header(str(kind), slice_index, reviewer, str(reviser), max_rounds)
    resolver = run_resolver(
        definition, model_override=None, params=params, pool_backend=DefaultPoolBackend()
    )
    try:
        # The revise dispatches' artifact post-condition reads the run's start time from
        # run state. This run is not resumable (D4), so the state is scratch: it lives in
        # a temp dir and `sq runs` never lists it.
        with tempfile.TemporaryDirectory(prefix="sq-review-revise-") as scratch:
            runs_dir = Path(scratch)
            run_id = StateManager(runs_dir=runs_dir).init_run(definition.name, params)
            async with pipeline_session(classification) as session:
                result = await execute_pipeline(
                    definition,
                    params,
                    resolver=resolver,
                    cf_client=ContextForgeClient(),
                    cwd=cwd,
                    run_id=run_id,
                    sdk_session=session,
                    pool_policy=classification.policy,
                    observer=printer,
                    runs_dir=runs_dir,
                )
    except GitEnvironmentError as exc:
        # Process boundary: a git fault (wrong branch, unreadable state) ends the run
        # with its message, as `sq run` does; the operator fixes the checkout.
        _logger.exception("review-revise halted by a git environment fault")
        typer.echo(f"Error: {exc}", err=True)
        return EXIT_RUN_FAILED
    outcome = outcome_of(result)
    if outcome.error is not None:
        typer.echo(outcome.error, err=True)
    if outcome.final_verdict is not None:
        noun = "round" if outcome.rounds == 1 else "rounds"
        typer.echo(f"final: {outcome.final_verdict} after {outcome.rounds} {noun}")
    return outcome.exit_code


def _refuse(message: str) -> typer.Exit:
    typer.echo(f"Error: {message}", err=True)
    return typer.Exit(EXIT_RUN_FAILED)


def refuse_revise_model_without_max(max_rounds: int | None, revise_model: str | None) -> None:
    """``--revise-model`` only means something to the revise loop (D6)."""
    if revise_model is not None and max_rounds is None:
        raise _refuse("--revise-model requires --max")


def validate_max_options(
    ctx: typer.Context, kind: BuiltinReviewTemplate, slice_input: str | None, *, cwd: str
) -> None:
    """Refuse a ``--max`` invocation the loop cannot honor, before any model call (D5, D6).

    Raises ``typer.Exit(1)`` after printing the reason to stderr.
    """
    if slice_input is None or not slice_input.isdigit():
        raise _refuse("--max requires a slice index")
    for param in ctx.command.params:
        # The positional index is an Argument and is exempt.
        if not isinstance(param, click.Option) or param.name is None:
            continue
        given = ctx.get_parameter_source(param.name) == ParameterSource.COMMANDLINE
        if given and param.name not in MAX_SUPPORTED_OPTIONS:
            raise _refuse(f"{param.opts[0]} is not supported with --max")
    _require_branch_preconditions(kind, int(slice_input), cwd)


def _require_branch_preconditions(kind: BuiltinReviewTemplate, slice_index: int, cwd: str) -> None:
    """Where the rounds will commit must be where this checkout is.

    ``slice`` and ``tasks`` rounds are planning commits, which only land on the integration
    target. ``code`` rounds commit to the checked-out slice branch and stage everything, so
    that branch must be the slice's and the tree clean.
    """
    cf_client = ContextForgeClient()
    try:
        if kind == BuiltinReviewTemplate.CODE:
            expected, _ = slice_facts(slice_index, cf_client)
        else:
            expected = read_integration_target(cf_client)
        if (actual := current_branch(cwd)) != expected:
            raise _refuse(
                f"--max for {kind} must run on branch {expected}, but {actual} is checked out"
            )
        if kind == BuiltinReviewTemplate.CODE and (paths := dirty_paths(cwd)):
            raise _refuse(f"working tree is not clean: {paths}. Commit or discard these, then rerun.")
    except (GitEnvironmentError, SliceNotInPlanError, NoDesignFileError) as exc:
        raise _refuse(str(exc)) from exc
