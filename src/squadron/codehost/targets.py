"""The pull-request target grammar.

Six forms, classified in a fixed order where each rule is exclusive of the ones
after it. The order is the specification, not an optimization: ``owner/repo#7``
must never fall through to the repository-name form, and ``7`` must never be
read as a branch.

The grammar lives here and nowhere else. ``pr.py`` passes the raw string
through; there is no pre-parsing at the CLI edge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from squadron.codehost.errors import TargetSyntaxError


class TargetForm(StrEnum):
    """Which of the six accepted shapes a target string matched."""

    CURRENT_BRANCH = "current_branch"
    URL = "url"
    OWNER_REPO_NUMBER = "owner_repo_number"
    REPO_NUMBER = "repo_number"
    NUMBER = "number"
    BRANCH = "branch"


@dataclass(frozen=True)
class PullRequestTarget:
    """A parsed target. Which fields are populated depends on ``form``."""

    form: TargetForm
    host: str | None = None
    owner: str | None = None
    repository: str | None = None
    number: int | None = None
    branch: str | None = None


#: ``/{owner}/{repo}/pull/{n}`` — the path shape of a pull-request URL.
_URL_PATH = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)")

#: ``owner/repo#n`` — exactly one slash before the ``#``, digits after.
_OWNER_REPO_NUMBER = re.compile(r"^([^/\s#]+)/([^/\s#]+)#(\d+)$")

#: ``repo#n`` — no slash, a non-empty name before the ``#``.
_REPO_NUMBER = re.compile(r"^([^/\s#]+)#(\d+)$")

#: ``7`` or ``#7``.
_NUMBER = re.compile(r"^#?(\d+)$")

#: Characters and shapes ``git check-ref-format --branch`` refuses. Applied as a
#: rejection test so rule 6 accepts anything git would accept as a branch name.
_INVALID_BRANCH = re.compile(
    r"""
      [\x00-\x20\x7f~^:?*\[\\]   # control chars, space, and git's reserved set
    | \.\.                        # no double dot
    | ^[./]                       # no leading dot or slash
    | [./]$                       # no trailing dot or slash
    | //                          # no empty path component
    | @\{                         # no reflog syntax
    | \.lock(?:/|$)               # no .lock component
    """,
    re.VERBOSE,
)


def _strip_url_suffixes(path: str) -> str:
    """Drop a trailing ``.git`` and any trailing slashes from a URL path."""
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return path


def _strip_repo_suffix(name: str) -> str:
    """Drop a trailing ``.git`` from a bare repository name."""
    return name[: -len(".git")] if name.endswith(".git") else name


def parse_target(text: str | None) -> PullRequestTarget:
    """Classify ``text`` into one of the six target forms.

    Raises ``TargetSyntaxError`` for a string valid under no rule.
    """
    # 1. Nothing supplied: resolve from the current branch.
    if text is None or not text.strip():
        return PullRequestTarget(form=TargetForm.CURRENT_BRANCH)

    candidate = text.strip()

    # 2. A URL, identified by its scheme. Query and fragment are discarded;
    #    a trailing .git or slash on the path is tolerated.
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        match = _URL_PATH.match(_strip_url_suffixes(parsed.path))
        if match is None:
            raise TargetSyntaxError(
                f"not a pull-request URL: {candidate}",
                fix_hint="Expected a URL ending in /{owner}/{repo}/pull/{number}.",
            )
        owner, repository, number = match.groups()
        return PullRequestTarget(
            form=TargetForm.URL,
            host=parsed.netloc,
            owner=owner,
            repository=_strip_repo_suffix(repository),
            number=int(number),
        )

    # 3. owner/repo#n
    match = _OWNER_REPO_NUMBER.match(candidate)
    if match is not None:
        owner, repository, number = match.groups()
        return PullRequestTarget(
            form=TargetForm.OWNER_REPO_NUMBER,
            owner=owner,
            repository=_strip_repo_suffix(repository),
            number=int(number),
        )

    # 4. repo#n
    match = _REPO_NUMBER.match(candidate)
    if match is not None:
        repository, number = match.groups()
        return PullRequestTarget(
            form=TargetForm.REPO_NUMBER,
            repository=_strip_repo_suffix(repository),
            number=int(number),
        )

    # 5. 7 or #7. A branch literally named "7" is unreachable by design:
    #    the number form wins, and that is intended.
    match = _NUMBER.match(candidate)
    if match is not None:
        return PullRequestTarget(form=TargetForm.NUMBER, number=int(match.group(1)))

    # 6. Anything git would accept as a branch name.
    if _INVALID_BRANCH.search(candidate):
        raise TargetSyntaxError(
            f"not a valid target: {candidate}",
            fix_hint=(
                "Expected a PR number, owner/repo#number, repo#number, a pull-request "
                "URL, or a branch name."
            ),
        )
    return PullRequestTarget(form=TargetForm.BRANCH, branch=candidate)
