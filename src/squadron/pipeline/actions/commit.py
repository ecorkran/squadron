"""Commit action — stages only the planned paths and commits them (slice 196).

What a commit stages and says comes from ``build_commit_plan``, the same builder
the hidden ``sq _commit`` command calls, so SDK and prompt-only runs agree.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import cast

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.commit_plan import (
    MESSAGE_PARAM,
    PATHS_PARAM,
    PLAN_PARAM,
    REVIEW_TEMPLATE_PARAM,
    SLICE_PARAM,
    SUBJECT_PARAM,
    CommitPlan,
    CommitSubject,
    CommitTarget,
    CommitTargetError,
    build_commit_plan,
)
from squadron.pipeline.git_ops import (
    ConfigReader,
    GitEnvironmentError,
    GitStateUnknownError,
    SliceNotInPlanError,
    current_branch,
    parse_slice_index,
    read_integration_target,
)
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pr.branch import parse_slice_branch
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)


class CommitAction:
    """Pipeline action that stages the planned files and creates a git commit."""

    @property
    def action_type(self) -> str:
        return ActionType.COMMIT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """Validate config structure. Actual cwd check happens at execute time."""
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        # git and cf run as subprocesses; keep them off the event loop.
        return await asyncio.to_thread(self._commit, context)

    def _commit(self, context: ActionContext) -> ActionResult:
        cwd = Path(context.cwd)
        try:
            target = _target_from_params(context)
        except ValueError as exc:
            return self._failure(str(exc))
        explicit_paths = _explicit_paths(context.params)

        if target is None:
            if not explicit_paths:
                return self._failure(
                    "commit needs a 'commit_subject' (a scoped commit) or explicit 'paths'; "
                    "refusing to stage everything"
                )
            plan_or_error = _explicit_plan(context, explicit_paths)
        else:
            plan_or_error = self._planned(target, cwd, context)
        if isinstance(plan_or_error, str):
            return self._failure(plan_or_error)
        plan = plan_or_error

        self._warn_left_out(context, plan)
        if not plan.paths:
            _logger.warning("commit: step %s produced no changes to commit", context.step_name)
            return ActionResult(
                success=True, action_type=self.action_type, outputs={"committed": False}
            )
        return self._stage_and_commit(plan, cwd)

    def _planned(self, target: CommitTarget, cwd: Path, context: ActionContext) -> CommitPlan | str:
        """The plan for a scoped commit, or the refusal text when its placement is wrong."""
        refusal = _check_placement(target, str(cwd), context.cf_client)
        if refusal is not None:
            return refusal
        try:
            plan = build_commit_plan(target, cwd, context.cf_client)
        except (CommitTargetError, SliceNotInPlanError, FileNotFoundError, ContextForgeError) as exc:
            # cf could not resolve the slice or plan, or a document is missing: an item
            # failure the batch can flag. Any other error is a fault and propagates.
            _logger.warning("commit: step %s cannot plan its commit: %s", context.step_name, exc)
            return str(exc)
        explicit_message = context.params.get(MESSAGE_PARAM)
        if explicit_message:
            # A caller-supplied message is a contract, not a template: used verbatim.
            return CommitPlan(plan.paths, plan.stage_all, str(explicit_message), plan.left_out)
        return plan

    def _stage_and_commit(self, plan: CommitPlan, cwd: Path) -> ActionResult:
        cwd_text = str(cwd)
        add_args = ["add", "-A"] if plan.stage_all else ["add", "--", *plan.paths]
        added = _run_or_unknown(add_args, cwd_text, "git add")
        if added.returncode != 0:
            return self._failure(added.stderr or "git add failed")

        # Limiting the commit to the planned paths keeps anything already in the
        # index (a stray `git add` by the operator) out of this commit.
        commit_args = ["commit", "-m", plan.message]
        if not plan.stage_all:
            commit_args += ["--", *plan.paths]
        committed = _run_or_unknown(commit_args, cwd_text, "git commit")
        if committed.returncode != 0:
            return self._failure(committed.stderr or "git commit failed")

        sha_result = run_git(["rev-parse", "HEAD"], cwd=cwd_text)
        if sha_result is None or sha_result.returncode != 0:
            _logger.warning("commit: committed, but cannot read the new HEAD sha")
            sha = "unknown"
        else:
            sha = sha_result.stdout.strip()
        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"committed": True, "sha": sha, "message": plan.message},
        )

    def _warn_left_out(self, context: ActionContext, plan: CommitPlan) -> None:
        if plan.left_out:
            _logger.warning(
                "commit: step %s left %d dirty path(s) out of the commit: %s",
                context.step_name,
                len(plan.left_out),
                ", ".join(plan.left_out),
            )

    def _failure(self, error: str) -> ActionResult:
        return ActionResult(success=False, action_type=self.action_type, outputs={}, error=error)


def _target_from_params(context: ActionContext) -> CommitTarget | None:
    """The commit target the step described, or ``None`` when it named no subject."""
    raw_subject = context.params.get(SUBJECT_PARAM)
    if raw_subject is None:
        return None
    subject = CommitSubject(str(raw_subject))  # ValueError names the bad subject
    raw_slice = context.params.get(SLICE_PARAM)
    raw_plan = context.params.get(PLAN_PARAM)
    raw_template = context.params.get(REVIEW_TEMPLATE_PARAM)
    return CommitTarget(
        subject=subject,
        slice_index=_slice_index(raw_slice),
        plan=str(raw_plan) if raw_plan not in (None, "") else None,
        review_template=str(raw_template) if raw_template else None,
        round=context.iteration,
    )


def _slice_index(raw: object) -> int | None:
    """The slice index a commit names, ``None`` when it names no slice."""
    if raw in (None, ""):
        return None
    try:
        return parse_slice_index(raw)
    except ValueError:
        raise ValueError(f"commit needs a slice index, got {raw!r}") from None


def _explicit_paths(params: dict[str, object]) -> list[str]:
    raw = params.get(PATHS_PARAM)
    if not raw or not isinstance(raw, list):
        return []
    return [str(p) for p in cast(list[object], raw)]


def _explicit_plan(context: ActionContext, paths: list[str]) -> CommitPlan | str:
    """A plan for a caller that named its own paths and message (user pipelines)."""
    message = context.params.get(MESSAGE_PARAM)
    if not message:
        return "commit with explicit 'paths' needs a 'message'"
    status = run_git(["status", "--porcelain", "--", *paths], cwd=context.cwd)
    if status is None or status.returncode != 0:
        return (status.stderr if status else "") or "git status failed — is this a git repository?"
    dirty = bool(status.stdout.strip())
    return CommitPlan(
        paths=tuple(paths) if dirty else (),
        stage_all=False,
        message=str(message),
        left_out=(),
    )


def _check_placement(target: CommitTarget, cwd: str, cf_client: ConfigReader) -> str | None:
    """Refuse a commit made from the wrong branch (D3, D8).

    Returns the refusal text for an item failure (code off its slice branch), or
    ``None`` when placement is right. A planning commit off the target raises:
    every later commit in the run would be misplaced too.
    """
    branch = current_branch(cwd)
    on_slice = parse_slice_branch(branch)
    if target.subject is CommitSubject.CODE:
        if target.slice_index is None:
            return "a code commit needs a slice index"
        if on_slice == target.slice_index:
            return None
        return f"refusing to stage all changes off the slice branch (on {branch})"

    integration = read_integration_target(cf_client)
    if branch == integration:
        return None
    # In a code pipeline the DEVLOG entry is written on the slice's own branch (D7).
    if (
        target.subject is CommitSubject.DEVLOG
        and target.slice_index is not None
        and on_slice == target.slice_index
    ):
        return None
    scope = (
        f"slice {target.slice_index}" if target.slice_index is not None else f"initiative {target.plan}"
    )
    raise GitEnvironmentError(f"planning commit for {scope} on {branch}; expected {integration}")


def _run_or_unknown(args: list[str], cwd: str, label: str) -> subprocess.CompletedProcess[str]:
    """Run git; a timeout means nobody knows whether the write landed (D6)."""
    result = run_git(args, cwd=cwd)
    if result is None:
        message = (
            f"{label} timed out or could not run: the index or an index.lock may be left "
            "in an unknown state"
        )
        _logger.error(message)
        raise GitStateUnknownError(message)
    return result


register_action(ActionType.COMMIT, CommitAction())
