"""The git facts the fix pipeline reads, behind one interface (slice 423).

``fix-context``, the fix commit and the prompt-only renderer all read the checked-out
branch, HEAD and the changed paths. They take a ``FixGit`` so one reader serves all
three and a test can hand in a fake instead of patching module functions.
"""

from __future__ import annotations

from typing import Protocol

from squadron.pipeline.git_ops import current_branch
from squadron.pipeline.guarded_commit import changed_paths
from squadron.pipeline.head_stamp import read_head


class FixGit(Protocol):
    def current_branch(self, cwd: str) -> str:
        """The checked-out branch or ``(detached HEAD)``; raises ``GitEnvironmentError``."""
        ...

    def head(self, cwd: str) -> str | None:
        """The sha HEAD names, or ``None`` when git cannot say."""
        ...

    def changed_paths(self, cwd: str) -> list[str] | str:
        """Every changed, staged or untracked path (ignored excluded), or the git error."""
        ...


class SubprocessFixGit:
    """The production reader: the shared git helpers, each bounded by a timeout."""

    def current_branch(self, cwd: str) -> str:
        return current_branch(cwd)

    def head(self, cwd: str) -> str | None:
        return read_head(cwd)

    def changed_paths(self, cwd: str) -> list[str] | str:
        return changed_paths(cwd)


#: The reader every fix component uses unless a caller hands in another.
SUBPROCESS_GIT: FixGit = SubprocessFixGit()
