"""The ``sq _commit --subject fix`` wiring (slice 423 D9).

Builds, from the command's flags and the report file, the same prior outputs the SDK
``commit`` action reads from a fix step, so ``CommitAction`` handles both modes alike.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.dispatch_io import RESPONSE_KEY
from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.fix_issue import parse_issue_ref
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    COMMIT_TO_VALUES,
    ISSUE_NUMBER_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
)
from squadron.pipeline.models import ActionResult, local_output_key

_logger = logging.getLogger(__name__)


class FixFlagsError(Exception):
    """The fix flags or report file are unusable; the message is the command's error."""


@dataclass(frozen=True)
class FixCommitFlags:
    """The five flags only a fix commit takes."""

    issue: str | None
    commit_to: str | None
    start_head: str | None
    start_branch: str | None
    report_file: str | None

    def named(self) -> dict[str, str | None]:
        return {
            "--issue": self.issue,
            "--commit-to": self.commit_to,
            "--start-head": self.start_head,
            "--start-branch": self.start_branch,
            "--report-file": self.report_file,
        }


def check_fix_flags(
    subject: CommitSubject | None, flags: FixCommitFlags, other_flags: Mapping[str, object]
) -> None:
    """Raise ``FixFlagsError`` unless the flags suit ``subject``.

    A fix commit takes all five fix flags, each well formed, and none of ``other_flags``
    (the scoped-commit flags, which it would otherwise silently ignore); any other
    subject takes none of the five.
    """
    named = flags.named()
    if subject is CommitSubject.FIX:
        missing = [flag for flag, value in named.items() if value is None]
        if missing:
            raise FixFlagsError(f"--subject fix requires {', '.join(missing)}")
        ignored = [flag for flag, value in other_flags.items() if value not in (None, [], 0)]
        if ignored:
            raise FixFlagsError(f"--subject fix does not take {', '.join(ignored)}")
        _check_fix_values(flags)
        return
    given = [flag for flag, value in named.items() if value is not None]
    if given:
        raise FixFlagsError(f"{', '.join(given)} only apply to --subject fix")


def _check_fix_values(flags: FixCommitFlags) -> None:
    """Reject a blank or unknown value at the command boundary, naming its flag."""
    if flags.commit_to not in COMMIT_TO_VALUES:
        allowed = list(COMMIT_TO_VALUES)
        raise FixFlagsError(f"--commit-to must be one of {allowed}, got {flags.commit_to!r}")
    for flag, value in (("--start-head", flags.start_head), ("--start-branch", flags.start_branch)):
        if value is None or not value.strip():
            raise FixFlagsError(f"{flag} must not be blank")


def fix_prior_outputs(flags: FixCommitFlags) -> dict[str, ActionResult]:
    """The ``fix-context`` and ``dispatch`` results a fix commit reads, from the flags.

    ``check_fix_flags`` has passed, so every flag is set.
    """
    assert flags.issue is not None and flags.report_file is not None
    try:
        issue_number = parse_issue_ref(flags.issue)
    except ValueError as exc:
        raise FixFlagsError(str(exc)) from exc
    report_path = Path(flags.report_file)
    try:
        reply = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _logger.exception("cannot read the report file '%s'", report_path)
        raise FixFlagsError(f"cannot read --report-file '{report_path}': {exc}") from exc
    context_result = ActionResult(
        success=True,
        action_type=ActionType.FIX_CONTEXT,
        outputs={
            ISSUE_NUMBER_KEY: issue_number,
            COMMIT_TO_KEY: flags.commit_to,
            START_HEAD_KEY: flags.start_head,
            START_BRANCH_KEY: flags.start_branch,
        },
    )
    reply_result = ActionResult(
        success=True, action_type=ActionType.DISPATCH, outputs={RESPONSE_KEY: reply}
    )
    return {
        local_output_key(ActionType.FIX_CONTEXT, 0): context_result,
        local_output_key(ActionType.DISPATCH, 1): reply_result,
    }
