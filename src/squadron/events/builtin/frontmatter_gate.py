"""squadron.frontmatter-gate — COMMIT action wrapping ``cf validate frontmatter``.

Refactors slice 172's bespoke installer-driven gate onto the events
mechanism (design D8). Exit mapping preserves 172's D6 posture: a gate that
cannot determine validity must not pass. Uses
``asyncio.create_subprocess_exec`` — never a blocking subprocess call inside
an async function (project async rule).

Slice 919 Part 3 (#98) adds three more indeterminate cases this same posture
covers: ``cf`` validating zero of N staged files (a sibling git worktree
resolving in-root against a different checkout, D10), an unreadable
``filesChecked`` count (D11), and a hung subprocess (D14) — each fails
closed with its own distinguishable message, since the operator's next
action differs for each cause.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import PurePosixPath
from typing import Any, cast

from squadron.core.process_group import kill_process_group
from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.tools import limits

_logger = logging.getLogger(__name__)

# cf's user-document root, defined once. Consulted only in the zero-of-N branch
# below (D2) — never used to pre-filter what gets sent to cf. Removal condition:
# this predicate goes away once cf validate frontmatter --json reports which
# staged paths it skipped as out of scope (filed upstream as
# ecorkran/context-forge#96).
_CF_DOCUMENT_ROOT = ("project-documents", "user")


def _is_under_cf_document_root(staged_path: str) -> bool:
    """Is `staged_path` (repo-root-relative, as the pre-commit hook passes it)
    under cf's user-document root?

    Compares normalized path parts rather than string prefixes, so
    `./project-documents/user/x.md` and `project-documents/user/x.md`
    classify identically.
    """
    parts = PurePosixPath(staged_path).parts
    return parts[: len(_CF_DOCUMENT_ROOT)] == _CF_DOCUMENT_ROOT


_MISSING_CF_MESSAGE = (
    "'cf' is not on PATH — cannot run cf validate frontmatter. "
    "Install context-forge, or disable this action in events.yaml."
)
_COULD_NOT_RUN_MESSAGE = (
    "cf could not run the validation — if this repo is not a registered cf "
    "project, run 'cf init' once, or disable this action in events.yaml."
)


def _worktree_cause_message(in_scope_count: int) -> str:
    return (
        f"cf validated 0 of {in_scope_count} in-scope staged file(s); in a git "
        "worktree this usually means cf resolved in-root against a different "
        "checkout, so the gate cannot confirm frontmatter and is failing closed."
    )


_UNREADABLE_COUNT_MESSAGE = (
    "cf validate frontmatter's --json output could not be read (missing or "
    "unparseable filesChecked) — the gate cannot confirm frontmatter and is "
    "failing closed. This looks like a cf version or output-shape problem, "
    "not a worktree problem."
)


class FrontmatterGateAction:
    """COMMIT event action: reject a commit whose staged markdown fails
    ``cf validate frontmatter``."""

    name = "squadron.frontmatter-gate"
    events = frozenset({EventType.COMMIT})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, CommitContext)

        args = ["cf", "validate", "frontmatter", "--json", *context.staged_paths]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=context.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Required so the timeout path can kill the whole group, not just cf itself.
                start_new_session=True,
            )
        except FileNotFoundError:
            _logger.warning("frontmatter-gate: %s", _MISSING_CF_MESSAGE)
            return ActionResult(
                success=False, action_type=self.name, outputs={}, error=_MISSING_CF_MESSAGE
            )

        # Read the limit at call time (module attribute), never captured at import, so a
        # lowered limit takes effect for the very next call — matches bash_tool.py.
        timeout = limits.FRONTMATTER_GATE_TIMEOUT_S
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            await kill_process_group(proc)
            message = f"cf validate frontmatter timed out after {timeout}s and was killed."
            _logger.warning("frontmatter-gate: %s", message)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=message)

        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")
        exit_code = proc.returncode

        if exit_code == 2:
            message = f"{_COULD_NOT_RUN_MESSAGE}\n{stdout}{stderr}".strip()
            _logger.warning("frontmatter-gate: %s", message)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=message)

        if exit_code not in (0, 1):
            message = stdout.strip() or stderr.strip() or f"cf validate frontmatter exited {exit_code}"
            _logger.warning("frontmatter-gate: %s", message)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=message)

        # D11: a hand-parsed count, never a silent fallback to exit-code-only behavior — the
        # same fail-closed posture as D10's worktree case and D14's timeout, for the same
        # reason: the gate could not confirm validity, so it must not pass.
        files_checked: int | None = None
        try:
            parsed: object = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            # json.loads yields Any; narrow once here so the accessor below is typed
            # (matches the pattern in codehost/github_cli.py).
            payload = cast(dict[str, Any], parsed)
            raw_count = payload.get("filesChecked")
            if isinstance(raw_count, int):
                files_checked = raw_count

        if files_checked is None:
            _logger.warning("frontmatter-gate: %s", _UNREADABLE_COUNT_MESSAGE)
            return ActionResult(
                success=False, action_type=self.name, outputs={}, error=_UNREADABLE_COUNT_MESSAGE
            )

        # D12: zero-checked is only a failure against non-empty staged input — a commit
        # staging no markdown gives cf nothing to check, and filesChecked: 0 is correct.
        # D2: cf silently skips paths outside its document scope, so filesChecked: 0
        # alone can't distinguish "wrong checkout" from "nothing staged was in scope".
        # All staged paths are still sent to cf above — this predicate is consulted
        # only here, to interpret the zero case.
        staged_count = len(context.staged_paths)
        if staged_count > 0 and files_checked == 0:
            in_scope_count = sum(1 for path in context.staged_paths if _is_under_cf_document_root(path))
            if in_scope_count == 0:
                return ActionResult(success=True, action_type=self.name, outputs={"stdout": stdout})
            message = _worktree_cause_message(in_scope_count)
            _logger.warning("frontmatter-gate: %s", message)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=message)

        if exit_code == 0:
            return ActionResult(success=True, action_type=self.name, outputs={"stdout": stdout})

        message = stdout.strip() or stderr.strip() or "cf validate frontmatter exited 1"
        _logger.warning("frontmatter-gate: %s", message)
        return ActionResult(success=False, action_type=self.name, outputs={}, error=message)


register_event_action(FrontmatterGateAction())
