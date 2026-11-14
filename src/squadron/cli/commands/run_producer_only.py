"""CLI side of ``sq run --producer-only`` (slice 424, D1, D3).

``run.py`` carries the flag and calls in here; the definition transform itself lives
in ``squadron.pipeline.producer_only``.
"""

from __future__ import annotations

import sys
from typing import TextIO

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.pipeline.actions import ActionType
from squadron.pipeline.commit_plan import SUBJECT_PARAM, CommitSubject
from squadron.pipeline.control_params import RUN_PRODUCER_ONLY
from squadron.pipeline.executor import PipelineResult, resolve_placeholders
from squadron.pipeline.git_ops import GitEnvironmentError, current_branch
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.producer_only import (
    ProducerOnlyError,
    ProducerOnlySelection,
    producer_only_definition,
)
from squadron.pipeline.state import ProducerOnlyRecord
from squadron.pipeline.steps import get_step_type
from squadron.pr.branch import parse_slice_branch

PRODUCER_ONLY_FLAG = "--producer-only"


def _error_exit(message: str) -> typer.Exit:
    """Print ``Error: <message>`` on stderr and return the exit to raise (no stack trace)."""
    rprint(f"[red]Error: {escape(message)}[/red]", file=sys.stderr)
    return typer.Exit(1)


def check_producer_only_flags(
    producer_only: bool,
    *,
    from_step: str | None,
    item: str | None,
    flagged: bool,
) -> None:
    """Refuse ``--producer-only`` beside a flag that addresses removed steps (D3).

    The run has one step, so ``--from`` has nothing to start from, and batch resume
    (``--item``, ``--flagged``) addresses steps the transform removed.
    """
    if not producer_only:
        return
    combined = (
        ("--from", from_step is not None),
        ("--item", item is not None),
        ("--flagged", flagged),
    )
    for flag, given in combined:
        if given:
            raise _error_exit(f"{PRODUCER_ONLY_FLAG} cannot be combined with {flag}.")


def apply_producer_only(
    definition: PipelineDefinition, params: dict[str, object]
) -> ProducerOnlySelection:
    """Narrow *definition* to its producer step and mark *params* so a resume repeats it.

    A pipeline without exactly one producer step ends the run here with an error.
    """
    try:
        selection = producer_only_definition(definition)
    except ProducerOnlyError as exc:
        raise _error_exit(str(exc)) from exc
    params[RUN_PRODUCER_ONLY] = True
    return selection


def producer_only_record(selection: ProducerOnlySelection) -> ProducerOnlyRecord:
    """The run-state record for *selection*."""
    return ProducerOnlyRecord(step=selection.step_name, skipped=list(selection.skipped))


def narrow_for_params(
    definition: PipelineDefinition, params: dict[str, object]
) -> ProducerOnlySelection | None:
    """The producer-only selection when *params* carry the flag, else ``None``.

    Every path that reloads a pipeline for a run (fresh, resume, prompt-only) calls
    this, so a producer-only run never grows its other steps back.
    """
    if not params.get(RUN_PRODUCER_ONLY):
        return None
    return producer_only_definition(definition)


def dry_run_line(selection: ProducerOnlySelection) -> str:
    """The extra line a producer-only dry run prints."""
    return f"producer-only: step {selection.step_name}; skipped: {', '.join(selection.skipped)}"


def stop_line(record: ProducerOnlyRecord, commit_sha: str | None) -> str:
    """The line printed when the run stops after its producer step.

    Built from the run-state record so a resumed run prints it too.
    """
    commit = f" (commit {commit_sha})" if commit_sha else ""
    return f"producer-only: stopped after {record.step}{commit}; skipped: {', '.join(record.skipped)}"


def commit_sha_of(result: PipelineResult) -> str | None:
    """The sha of the commit the run made, or ``None`` when it made none."""
    for step_result in result.step_results:
        for action_result in step_result.action_results:
            if action_result.action_type != ActionType.COMMIT:
                continue
            if action_result.outputs.get("committed") is True:
                return str(action_result.outputs["sha"])
    return None


def print_stop_line(
    result: PipelineResult, record: ProducerOnlyRecord | None, file: TextIO | None = None
) -> None:
    """Print the stop line once for a producer-only run; nothing for any other run.

    *file* defaults to stdout; a prompt-only run passes stderr to keep its JSON clean.
    """
    if record is not None:
        rprint(escape(stop_line(record, commit_sha_of(result))), file=file)


def check_code_branch(selection: ProducerOnlySelection, params: dict[str, object], cwd: str) -> None:
    """Refuse a code-committing producer step off its slice branch, before any dispatch.

    ``P6`` enters the slice branch in its first step, which producer-only does not run,
    and ``implement``'s commit refuses off the branch only after the dispatch has spent
    (slice 424 task notes). Steps whose commit is not a code commit are not checked.
    """
    step = selection.definition.steps[0]
    # The expansion adds ``slice: '{slice}'`` itself, so resolve each expanded action
    # the way the executor does, not the step's own config.
    for action_type, raw_config in get_step_type(step.step_type).expand(step):
        config = resolve_placeholders(raw_config, params)
        if action_type != ActionType.COMMIT or config.get(SUBJECT_PARAM) != CommitSubject.CODE:
            continue
        try:
            slice_index = int(str(config.get("slice")))
        except ValueError:
            raise _error_exit(
                f"{PRODUCER_ONLY_FLAG} needs an integer slice index for a code commit; "
                f"got '{config.get('slice')}'."
            ) from None
        try:
            branch = current_branch(cwd)
        except GitEnvironmentError as exc:
            raise _error_exit(str(exc)) from exc
        if parse_slice_branch(branch) != slice_index:
            raise _error_exit(
                f"{PRODUCER_ONLY_FLAG} does not run branch: enter; "
                f"check out the branch for slice {slice_index} first (on {branch})."
            )
