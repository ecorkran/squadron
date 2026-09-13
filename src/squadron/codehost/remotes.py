"""Git remote enumeration and target-to-remote selection.

Selection is host-agnostic: it never imports a host implementation. Whether a
remote belongs to a host worth considering is asked through a ``serves_host``
callable supplied by the caller, so a checkout carrying remotes on several
hosts resolves correctly without this module knowing what any of them are.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence

from squadron.codehost.errors import (
    AmbiguousHostRemoteError,
    ForeignRepositoryError,
    NoHostRemoteError,
)
from squadron.codehost.models import LocalRemote, RepositoryLocator
from squadron.codehost.targets import PullRequestTarget, TargetForm
from squadron.core.process_runner import ProcessRunner

_logger = logging.getLogger(__name__)

#: Wall-clock bound on the git queries this module runs. Matches the value in
#: ``squadron.review.git_utils`` but is deliberately not imported from it —
#: ``codehost`` must not depend on ``review``.
GIT_QUERY_TIMEOUT_SECONDS = 30

#: ``https://host/owner/repo(.git)`` and ``ssh://git@host/owner/repo(.git)``.
_URL_REMOTE = re.compile(
    r"^(?:https?|ssh)://(?:[^@/]+@)?(?P<host>[^/:]+)(?::\d+)?/"
    r"(?P<owner>[^/]+)/(?P<repository>[^/]+?)(?:\.git)?/?$"
)

#: The scp-like shorthand ``git@host:owner/repo(.git)``.
_SCP_REMOTE = re.compile(
    r"^(?:[^@/]+@)?(?P<host>[^/:]+):(?P<owner>[^/]+)/(?P<repository>[^/]+?)(?:\.git)?/?$"
)


def parse_remote_url(name: str, url: str) -> LocalRemote:
    """Parse a remote URL into coordinates, or record that it could not be.

    A URL matching no known shape yields ``host=None``. Such a remote is never
    a selection candidate, but it is retained so ambiguity messages can name it
    — dropping it silently is the failure mode this guards against.
    """
    for pattern in (_URL_REMOTE, _SCP_REMOTE):
        match = pattern.match(url.strip())
        if match is not None:
            return LocalRemote(
                name=name,
                host=match.group("host"),
                owner=match.group("owner"),
                repository=match.group("repository"),
                url=url,
            )
    return LocalRemote(name=name, host=None, owner=None, repository=None, url=url)


def list_remotes(runner: ProcessRunner, cwd: str) -> list[LocalRemote]:
    """Enumerate the repository's remotes in ``git remote`` order."""
    listing = runner.run(["git", "remote"], cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    remotes: list[LocalRemote] = []
    for name in (line.strip() for line in listing.stdout.splitlines()):
        if not name:
            continue
        url_result = runner.run(
            ["git", "remote", "get-url", name],
            cwd=cwd,
            timeout=GIT_QUERY_TIMEOUT_SECONDS,
        )
        remotes.append(parse_remote_url(name, url_result.stdout.strip()))
    return remotes


def _locator(remote: LocalRemote) -> RepositoryLocator:
    """Build a locator from a remote already known to have parsed.

    Every caller filters to parsed remotes first, so reaching here with a
    missing field is a bug in this module. Raised rather than asserted: an
    ``assert`` disappears under ``python -O``, which would turn that bug into a
    locator carrying ``None`` coordinates and a silent failure downstream.
    """
    if remote.host is None or remote.owner is None or remote.repository is None:
        raise ValueError(
            f"remote {remote.name!r} reached selection without parsed coordinates: {remote.url!r}"
        )
    return RepositoryLocator(
        host=remote.host,
        owner=remote.owner,
        repository=remote.repository,
        remote_name=remote.name,
    )


def _describe(remotes: Sequence[LocalRemote]) -> str:
    """Name every remote and what it points at, unparseable ones included."""
    parts: list[str] = []
    for remote in remotes:
        if remote.owner is None or remote.repository is None:
            parts.append(f"{remote.name} (unrecognized URL: {remote.url})")
        else:
            parts.append(f"{remote.name} -> {remote.owner}/{remote.repository}")
    return ", ".join(parts)


def _matches(value: str | None, expected: str | None) -> bool:
    """Case-insensitive comparison that never matches on a missing value."""
    return value is not None and expected is not None and value.lower() == expected.lower()


def select_remote(
    target: PullRequestTarget,
    remotes: Sequence[LocalRemote],
    serves_host: Callable[[str], bool],
) -> RepositoryLocator:
    """Choose the remote a target refers to.

    Three branches by target form: explicit forms name a repository outright,
    the repository-name form ignores the owner, and bare forms rely entirely on
    which remotes belong to a served host.
    """
    if target.form in (TargetForm.URL, TargetForm.OWNER_REPO_NUMBER):
        return _select_explicit(target, remotes)
    if target.form is TargetForm.REPO_NUMBER:
        return _select_by_repository_name(target, remotes, serves_host)
    return _select_bare(remotes, serves_host)


def _select_explicit(target: PullRequestTarget, remotes: Sequence[LocalRemote]) -> RepositoryLocator:
    """Owner and repository both named; host too when the form carries one."""
    candidates = [
        remote
        for remote in remotes
        if _matches(remote.owner, target.owner)
        and _matches(remote.repository, target.repository)
        and (target.host is None or _matches(remote.host, target.host))
    ]
    if not candidates:
        raise ForeignRepositoryError(
            f"no remote points at {target.owner}/{target.repository}; "
            f"remotes are: {_describe(remotes)}",
            fix_hint="Add a remote for that repository, or review it from a checkout that has one.",
        )
    if len(candidates) > 1:
        # Several remotes for one repository is normal (a fork plus its
        # upstream, or a mirror). Taking git's own order is deterministic, but
        # the operator should be able to see which one was used.
        _logger.info(
            "%s remotes match %s/%s; using %s",
            len(candidates),
            target.owner,
            target.repository,
            candidates[0].name,
        )
    return _locator(candidates[0])


def _select_by_repository_name(
    target: PullRequestTarget,
    remotes: Sequence[LocalRemote],
    serves_host: Callable[[str], bool],
) -> RepositoryLocator:
    """Repository named without an owner: the host must narrow it to one."""
    candidates = [
        remote
        for remote in remotes
        if remote.host is not None
        and serves_host(remote.host)
        and _matches(remote.repository, target.repository)
    ]
    if not candidates:
        raise ForeignRepositoryError(
            f"no remote on a served host points at a repository named "
            f"{target.repository}; remotes are: {_describe(remotes)}",
            fix_hint="Use the owner/repo#number form, or add a remote for that repository.",
        )
    owners = {remote.owner.lower() for remote in candidates if remote.owner is not None}
    if len(owners) > 1:
        listed = ", ".join(f"{remote.owner}/{remote.repository}" for remote in candidates)
        raise AmbiguousHostRemoteError(
            f"{target.repository} matches several owners: {listed}",
            fix_hint="Name the owner explicitly with the owner/repo#number form.",
        )
    return _locator(candidates[0])


def _select_bare(
    remotes: Sequence[LocalRemote], serves_host: Callable[[str], bool]
) -> RepositoryLocator:
    """Nothing named: exactly one remote on a served host is required.

    This is why ``serves_host`` exists. A naive "exactly one remote" rule gets
    the common GitHub-plus-mirror layout wrong.
    """
    candidates = [remote for remote in remotes if remote.host is not None and serves_host(remote.host)]
    if not candidates:
        raise NoHostRemoteError(
            f"no remote belongs to a supported host; remotes are: {_describe(remotes)}",
            fix_hint="Add a remote on a supported host, or name the pull request by URL.",
        )
    if len(candidates) > 1:
        listed = ", ".join(remote.name for remote in candidates)
        raise AmbiguousHostRemoteError(
            f"several remotes could serve this target: {listed}",
            fix_hint="Name the repository explicitly, for example owner/repo#number.",
        )
    return _locator(candidates[0])
