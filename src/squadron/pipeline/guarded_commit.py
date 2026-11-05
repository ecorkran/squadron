"""The guarded ``commit`` step's checks and plan (#292).

A run in someone else's checkout (Amoeba's slice-writing pipeline) may commit only the
files it was asked to write. Before anything is staged: the branch must be the
integration target, HEAD must still be where the run started, and every changed or
untracked file must match one of the step's ``paths`` globs. A file outside them fails
the step, naming it; nothing is staged.
"""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase

from squadron.pipeline.commit_plan import CommitPlan
from squadron.pipeline.git_ops import ConfigReader, current_branch, read_integration_target
from squadron.pipeline.head_stamp import read_head
from squadron.review.git_utils import run_git

# The commit action runs the guarded path when its config carries this key; only the
# ``commit`` step type sets it.
GUARDED_PARAM = "commit_guarded"

# Porcelain v1 status codes whose entry is followed by the original path (-z form).
_RENAME_OR_COPY = frozenset({"R", "C"})


def changed_paths(cwd: str) -> list[str] | str:
    """Every changed, staged or untracked path (ignored files excluded), or the git error."""
    status = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=cwd)
    if status is None or status.returncode != 0:
        return (status.stderr if status else "") or "git status failed — is this a git repository?"
    fields = status.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue  # the trailing empty field after the last NUL
        paths.append(entry[3:])
        if entry[0] in _RENAME_OR_COPY:
            # The original path follows as its own field; its deletion is part of the change.
            paths.append(fields[index])
            index += 1
    return paths


def outside_globs(paths: Sequence[str], globs: Sequence[str]) -> list[str]:
    """The paths no glob matches. ``*`` crosses ``/``, as in ``fnmatch``."""
    return [path for path in paths if not any(fnmatchcase(path, glob) for glob in globs)]


def guarded_plan(
    *,
    cwd: str,
    globs: Sequence[str],
    message: str,
    start_head: object,
    cf_client: ConfigReader,
) -> CommitPlan | str:
    """The plan for a guarded commit, or why it is refused.

    An empty plan (no changes) is not a refusal: the step succeeds with no commit.
    """
    if not message:
        return "commit step needs a 'message'"
    if not globs:
        return "commit step needs 'paths'"
    if not isinstance(start_head, str) or not start_head:
        return "cannot check HEAD: the run did not record its starting commit (not a git repository?)"
    branch = current_branch(cwd)
    target = read_integration_target(cf_client)
    if branch != target:
        return f"refusing to commit on {branch}; commits go on the integration target {target}"
    head = read_head(cwd)
    if head != start_head:
        now = (head or "unknown")[:12]
        return (
            f"HEAD moved during the run (started at {start_head[:12]}, now {now}); "
            "something else committed or switched branches"
        )
    changed = changed_paths(cwd)
    if isinstance(changed, str):
        return changed
    if stray := outside_globs(changed, globs):
        return f"changed files outside the commit step's paths: {', '.join(stray)}"
    return CommitPlan(paths=tuple(changed), stage_all=False, message=message, left_out=())
