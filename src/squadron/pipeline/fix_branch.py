"""Whether the checked-out branch can take a fix commit (slice 423 D5).

One check behind ``fix-context`` (before the dispatch), the fix commit (after it) and the
prompt-only renderer, so the three refuse the same states with the same words.
"""

from __future__ import annotations

from squadron.pipeline.fix_keys import CommitTo
from squadron.pipeline.git_ops import DETACHED_HEAD, ConfigReader, read_integration_target

DETACHED_MESSAGE = "HEAD is detached; a fix commits to a branch"


def branch_problem(
    branch: str,
    commit_to: CommitTo,
    cf_client: ConfigReader,
    *,
    start_branch: str | None = None,
) -> str | None:
    """Why ``branch`` cannot take the fix, or ``None``.

    ``start_branch`` is the branch the fix started on; the commit passes it so a switch
    during the dispatch is caught. ``cf_client`` is read only under ``commit-to: target``,
    and a cf failure raises ``GitEnvironmentError`` rather than refusing.
    """
    if branch == DETACHED_HEAD:
        return DETACHED_MESSAGE
    if start_branch is not None and branch != start_branch:
        return f"branch changed from '{start_branch}' to '{branch}' during the fix"
    if commit_to is CommitTo.TARGET:
        target = read_integration_target(cf_client)
        if branch != target:
            return f"commit-to target requires branch '{target}', but '{branch}' is checked out"
    return None
