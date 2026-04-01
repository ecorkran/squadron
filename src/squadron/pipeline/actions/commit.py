"""Commit action — stages and commits changes via git."""

from __future__ import annotations

import subprocess
from typing import cast

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


class CommitAction:
    """Pipeline action that stages files and creates a git commit."""

    @property
    def action_type(self) -> str:
        return ActionType.COMMIT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """Validate config structure. Actual cwd check happens at execute time."""
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        cwd = context.cwd

        # Check for changes
        status = _git(["status", "--porcelain"], cwd=cwd)
        if status is None or status.returncode != 0:
            stderr = status.stderr if status else "git status failed"
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=stderr or "git status failed — is this a git repository?",
            )

        if not status.stdout.strip():
            return ActionResult(
                success=True,
                action_type=self.action_type,
                outputs={"committed": False},
            )

        # Stage files
        paths_raw = context.params.get("paths")
        if paths_raw and isinstance(paths_raw, list):
            stage_result = _git(
                ["add", *(str(p) for p in cast(list[object], paths_raw))],
                cwd=cwd,
            )
        else:
            stage_result = _git(["add", "-A"], cwd=cwd)

        if stage_result is None or stage_result.returncode != 0:
            stderr = stage_result.stderr if stage_result else "git add failed"
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=stderr,
            )

        # Build commit message
        message = context.params.get("message")
        if not message:
            commit_type = context.params.get("type", "chore")
            message = f"{commit_type}: {context.step_name} for {context.pipeline_name}"
        message = str(message)

        # Commit
        commit_result = _git(["commit", "-m", message], cwd=cwd)
        if commit_result is None or commit_result.returncode != 0:
            stderr = commit_result.stderr if commit_result else "git commit failed"
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=stderr,
            )

        # Get SHA
        sha_result = _git(["rev-parse", "HEAD"], cwd=cwd)
        sha = sha_result.stdout.strip() if sha_result else "unknown"

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={
                "committed": True,
                "sha": sha,
                "message": message,
            },
        )


def _git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
    """Run a git command, returning the CompletedProcess or None on error."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except OSError:
        return None


register_action(ActionType.COMMIT, CommitAction())
