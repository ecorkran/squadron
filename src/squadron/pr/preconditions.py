"""The pushed-branch precondition (D2): missing vs. behind, two different fixes.

``sq pr create`` never pushes. Both checks run before any model call and
before the only write.
"""

from __future__ import annotations

from squadron.codehost.errors import CodeHostError, HostCommandTimeoutError
from squadron.codehost.models import RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import ProcessNotFoundError, ProcessTimedOutError


class HeadBranchMissingError(CodeHostError):
    """The head branch has not been pushed to the host."""


class HeadBranchBehindError(CodeHostError):
    """The host's copy of the head branch is not the commit being described."""


class GitUnavailableError(CodeHostError):
    """The local ``git`` binary could not be invoked at all."""


def check_head_pushed(
    host: CodeHost,
    locator: RepositoryLocator,
    *,
    head: str,
    local_sha: str,
    cwd: str,
) -> None:
    """Refuse when *head* is missing from the host, or behind local.

    Missing: ``branch_exists`` is false. The fix is
    ``git push -u <remote> <head>``.

    Behind: the branch exists, but the host's sha for it differs from
    ``local_sha``. The fix is ``git push <remote> <head>``.

    The remote sha comes from ``git ls-remote`` through the adapter's own
    process-runner seam, bounded by ``GIT_QUERY_TIMEOUT_SECONDS`` — a git
    query, not a ``gh`` call, so it is not bounded by
    ``HOST_COMMAND_TIMEOUT_SECONDS`` (D2).
    """
    if not host.branch_exists(locator, head):
        raise HeadBranchMissingError(
            f"Branch {head!r} has not been pushed to "
            f"{locator.host}/{locator.owner}/{locator.repository}.",
            fix_hint=f"git push -u {locator.remote_name} {head}",
        )

    remote_sha = _remote_head_sha(host, locator, head=head, cwd=cwd)
    if remote_sha != local_sha:
        raise HeadBranchBehindError(
            f"Branch {head!r} on the host is at {remote_sha!r}, but local is "
            f"at {local_sha!r}.",
            fix_hint=f"git push {locator.remote_name} {head}",
        )


def _remote_head_sha(host: CodeHost, locator: RepositoryLocator, *, head: str, cwd: str) -> str | None:
    """The sha the host reports for ``head``, or ``None`` if it reports none."""
    argv = ["git", "ls-remote", locator.remote_name, f"refs/heads/{head}"]
    try:
        result = host.runner.run(argv, cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    except ProcessNotFoundError as exc:
        raise GitUnavailableError(
            "git is not on PATH", fix_hint="Install git and ensure it is on PATH."
        ) from exc
    except ProcessTimedOutError as exc:
        raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc

    if result.returncode != 0 or not result.stdout.strip():
        return None
    line = result.stdout.splitlines()[0]
    sha, _, _ = line.partition("\t")
    return sha.strip() or None
