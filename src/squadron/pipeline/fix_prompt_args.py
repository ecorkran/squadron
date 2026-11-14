"""The command lines prompt-only mode renders for a fix step (slice 423 D9).

``fix-context`` becomes ``sq _fix-prompt …`` and the fix ``commit`` becomes
``sq _commit --subject fix …``: both run the same code the SDK actions run.
"""

from __future__ import annotations

from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.fix_branch import DETACHED_MESSAGE
from squadron.pipeline.fix_git import SUBPROCESS_GIT, FixGit
from squadron.pipeline.fix_keys import COMMIT_TO_PARAM, ISSUE_FILE_PARAM, ISSUE_PARAM
from squadron.pipeline.git_ops import DETACHED_HEAD

# The harness replaces this with the temp file the session writes its final report to.
REPORT_PATH_PLACEHOLDER = "{tmp_path}"


class FixRenderError(ValueError):
    """The fix step cannot be rendered for prompt-only mode; the message says why."""


def _required(config: dict[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str | int) or str(value).strip() == "":
        raise FixRenderError(f"fix step has no '{key}' to render, got {value!r}")
    return str(value)


def fix_context_args(config: dict[str, object]) -> list[str]:
    """``sq _fix-prompt``'s argv for a resolved ``fix-context`` config.

    ``--io-dir`` is never passed: ``sq run --prompt-only`` refuses it.
    """
    args = ["sq", "_fix-prompt", "--issue", _required(config, ISSUE_PARAM)]
    issue_file = config.get(ISSUE_FILE_PARAM)
    if issue_file:
        args += ["--issue-file", str(issue_file)]
    return [*args, "--commit-to", _required(config, COMMIT_TO_PARAM)]


def fix_commit_args(
    context_config: dict[str, object], cwd: str | None, git: FixGit = SUBPROCESS_GIT
) -> list[str]:
    """``sq _commit``'s argv for the fix commit, with HEAD and branch read now.

    They are read once, when the step's instructions are built and before the session
    runs anything, so an agent commit or branch switch during the dispatch is caught.
    """
    if cwd is None:
        raise FixRenderError("the fix commit needs the working directory to record HEAD and the branch")
    head = git.head(cwd)
    if head is None:
        raise FixRenderError("cannot read HEAD; the fix commit has no start point to check")
    branch = git.current_branch(cwd)
    if branch == DETACHED_HEAD:
        raise FixRenderError(DETACHED_MESSAGE)
    return [
        "sq",
        "_commit",
        "--subject",
        CommitSubject.FIX.value,
        "--issue",
        _required(context_config, ISSUE_PARAM),
        "--commit-to",
        _required(context_config, COMMIT_TO_PARAM),
        "--start-head",
        head,
        "--start-branch",
        branch,
        "--report-file",
        REPORT_PATH_PLACEHOLDER,
    ]
