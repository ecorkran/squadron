"""The fix-context action: issue text, preconditions and the assembled prompt (slice 423 D2, D5).

Runs before the dispatch. Every refusal here happens before any model call, and the
clean-tree check is what makes the fix commit's stage-everything safe. The outputs carry
``operation: build_context`` and ``stdout`` so the dispatch finds the prompt through its
existing fallback, and the start point the commit action later checks.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from squadron.codehost.github_cli import build_github_host
from squadron.core.process_runner import SubprocessRunner
from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.actions.cf_op import CfOperation
from squadron.pipeline.actions.dispatch_io import io_dir
from squadron.pipeline.fix_branch import branch_problem
from squadron.pipeline.fix_git import SUBPROCESS_GIT, FixGit
from squadron.pipeline.fix_issue import (
    IssueLoader,
    IssueTextError,
    IssueTextLoader,
    parse_issue_ref,
    render_fix_prompt,
)
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    COMMIT_TO_PARAM,
    COMMIT_TO_VALUES,
    ISSUE_FILE_PARAM,
    ISSUE_NUMBER_KEY,
    ISSUE_PARAM,
    ISSUE_SOURCE_KEY,
    ISSUE_TEXT_SHA256_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
    CommitTo,
)
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_logger = logging.getLogger(__name__)

# The output key and value the dispatch's prompt fallback looks for (the same pair
# ``cf-op(build_context)`` writes).
OPERATION_KEY = "operation"
PROMPT_KEY = "stdout"


class FixContextAction:
    """Checks a fix may start, reads the issue, and assembles the fix prompt."""

    def __init__(self, loader: IssueLoader | None = None, git: FixGit = SUBPROCESS_GIT) -> None:
        self._git = git
        # The default builds a GitHub host only when it must fetch; file mode never does.
        self._loader: IssueLoader = loader or IssueTextLoader(
            lambda: build_github_host(SubprocessRunner())
        )

    @property
    def action_type(self) -> str:
        return ActionType.FIX_CONTEXT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """The step type validates its keys; the run-time values are checked at execute."""
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        # git and the issue source run as subprocesses or file reads; keep them off the loop.
        return await asyncio.to_thread(self._run, context)

    def _run(self, context: ActionContext) -> ActionResult:
        params = context.params
        try:
            issue_number = parse_issue_ref(str(params.get(ISSUE_PARAM, "")))
        except ValueError as exc:
            return self._refuse(str(exc))
        raw_commit_to = str(params.get(COMMIT_TO_PARAM))
        try:
            commit_to = CommitTo(raw_commit_to)
        except ValueError:
            allowed = ", ".join(COMMIT_TO_VALUES)
            return self._refuse(f"commit-to must be one of {allowed}, got {raw_commit_to!r}")

        if (problem := self._dirty_tree(context.cwd)) is not None:
            return self._refuse(problem)
        branch = self._git.current_branch(context.cwd)  # a GitEnvironmentError ends the run
        if (problem := branch_problem(branch, commit_to, context.cf_client)) is not None:
            return self._refuse(problem)
        head = self._git.head(context.cwd)
        if head is None:
            return self._refuse("cannot read HEAD: there is no start point to record")

        try:
            issue = self._loader.load(
                issue_number,
                str(params.get(ISSUE_FILE_PARAM) or ""),
                Path(io_dir(params, context.cwd)),
                context.cwd,
            )
        except IssueTextError as exc:
            # Logged where it was raised and carries the cause; here it is only reported.
            return ActionResult(success=False, action_type=self.action_type, outputs={}, error=str(exc))
        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={
                OPERATION_KEY: CfOperation.BUILD_CONTEXT.value,
                PROMPT_KEY: render_fix_prompt(issue_number, issue.text),
                ISSUE_NUMBER_KEY: issue_number,
                ISSUE_SOURCE_KEY: issue.source.value,
                ISSUE_TEXT_SHA256_KEY: issue.sha256,
                START_HEAD_KEY: head,
                START_BRANCH_KEY: branch,
                COMMIT_TO_KEY: commit_to.value,
            },
        )

    def _dirty_tree(self, cwd: str) -> str | None:
        """Why the tree is not clean, or ``None``: the fix commit stages every change."""
        paths = self._git.changed_paths(cwd)
        if isinstance(paths, str):
            return f"cannot read the working tree state: {paths.strip()}"
        if paths:
            return "the working tree has uncommitted changes: " + ", ".join(paths)
        return None

    def _refuse(self, message: str) -> ActionResult:
        _logger.warning("fix-context refused: %s", message)
        return ActionResult(success=False, action_type=self.action_type, outputs={}, error=message)


register_action(ActionType.FIX_CONTEXT, FixContextAction())
