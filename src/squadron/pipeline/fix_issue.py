"""The issue a fix works from: its reference and its text (slice 423 D2).

``parse_issue_ref`` turns ``301`` or ``#301`` into a number. ``IssueTextLoader`` reads
the text from a frozen file, or fetches the issue and every comment through the code host.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.codehost.errors import CodeHostError
from squadron.codehost.issue_text import render_issue
from squadron.codehost.models import RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import LocalRemote, list_remotes, select_remote
from squadron.codehost.targets import PullRequestTarget, TargetForm
from squadron.data import data_dir
from squadron.pipeline.dispatch_keys import path_error
from squadron.pipeline.fix_keys import IssueSource

_logger = logging.getLogger(__name__)

# The packaged fix prompt and the two placeholders it holds (D8).
FIX_PROMPT_PATH = ("prompts", "fix.md")
ISSUE_NUMBER_PLACEHOLDER = "{issue_number}"
ISSUE_TEXT_PLACEHOLDER = "{issue_text}"


class IssueTextError(Exception):
    """The issue text could not be obtained; the message names the cause."""


@dataclass(frozen=True)
class IssueText:
    """An issue's text, where it came from, and the hash of its UTF-8 bytes."""

    text: str
    source: IssueSource
    sha256: str


class IssueLoader(Protocol):
    """Supplies the issue text for ``fix-context``."""

    def load(self, issue_number: int, issue_file: str, io_dir: Path | None, cwd: str) -> IssueText:
        """Read ``issue_file`` when non-empty, else fetch ``issue_number`` for the repo at ``cwd``."""
        ...


def parse_issue_ref(value: str) -> int:
    """A positive integer with an optional leading ``#``; anything else is a ``ValueError``."""
    digits = value.strip().removeprefix("#")
    if not digits.isascii() or not digits.isdigit() or int(digits) < 1:
        raise ValueError(f"issue must be a positive integer, optionally prefixed with '#': {value!r}")
    return int(digits)


def _refusal(message: str) -> IssueTextError:
    """A checked refusal: logged at WARNING, then raised by the caller."""
    _logger.warning("%s", message)
    return IssueTextError(message)


class IssueTextLoader:
    """Loads issue text from a frozen file, or through the code host (slice 423 D2, D3)."""

    def __init__(self, host_factory: Callable[[], CodeHost]) -> None:
        # Called only in fetch mode, so file mode never builds a host.
        self._host_factory = host_factory

    def load(self, issue_number: int, issue_file: str, io_dir: Path | None, cwd: str) -> IssueText:
        if issue_file:
            return self._read_file(issue_file, io_dir, cwd)
        return self._fetch(issue_number, cwd)

    def _fetch(self, issue_number: int, cwd: str) -> IssueText:
        """The issue and every comment, no cutoff (D3): a live fix has no answer to hide."""
        target = PullRequestTarget(form=TargetForm.NUMBER, number=issue_number)
        try:
            host = self._host_factory()
            remotes = list_remotes(host.runner, cwd)
            locator = self._select(target, remotes, host)
            snapshot = host.get_issue(locator, issue_number)
        except CodeHostError as exc:
            # No retry and no fallback to a file: the action reports this before any dispatch.
            _logger.exception("cannot fetch issue #%d", issue_number)
            hint = f" ({exc.fix_hint})" if exc.fix_hint else ""
            raise IssueTextError(f"cannot fetch issue #{issue_number}: {exc}{hint}") from exc
        text = render_issue(snapshot, None)
        return IssueText(text, IssueSource.GITHUB, hashlib.sha256(text.encode("utf-8")).hexdigest())

    @staticmethod
    def _select(
        target: PullRequestTarget, remotes: Sequence[LocalRemote], host: CodeHost
    ) -> RepositoryLocator:
        """The repository holding the issue, by the bare ``#n`` rule.

        The selection's own remediation hints name the ``owner/repo#number`` form, which
        ``fix`` does not accept, so they are left out of the refusal; its message stays.
        """
        try:
            return select_remote(target, remotes, host.serves_host)
        except CodeHostError as exc:
            _logger.exception("cannot select the repository for issue #%s", target.number)
            raise IssueTextError(f"cannot fetch issue #{target.number}: {exc}") from exc

    def _read_file(self, issue_file: str, io_dir: Path | None, cwd: str) -> IssueText:
        problem = path_error(issue_file)
        if problem is not None:
            raise _refusal(f"issue-file: {problem}")
        path = (io_dir if io_dir is not None else Path(cwd)) / issue_file
        if not path.exists():
            raise _refusal(f"issue-file '{path}' does not exist")
        if not path.is_file():
            raise _refusal(f"issue-file '{path}' is not a regular file")
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _logger.exception("cannot read issue-file '%s'", path)
            raise IssueTextError(f"cannot read issue-file '{path}': {exc}") from exc
        if not text.strip():
            raise _refusal(f"issue-file '{path}' is empty")
        return IssueText(text, IssueSource.FILE, hashlib.sha256(raw).hexdigest())


def render_fix_prompt(issue_number: int, issue_text: str) -> str:
    """The packaged fix prompt with the issue number and text substituted.

    Plain ``str.replace``, number first and text last, so braces inside the issue text,
    even a literal placeholder, are never substituted or read as format fields.
    """
    template = data_dir().joinpath(*FIX_PROMPT_PATH).read_text(encoding="utf-8")
    return template.replace(ISSUE_NUMBER_PLACEHOLDER, str(issue_number)).replace(
        ISSUE_TEXT_PLACEHOLDER, issue_text
    )
