"""A ``FixGit`` for tests: the real readers, with any one of them replaced (slice 423)."""

from __future__ import annotations

from collections.abc import Callable

from squadron.pipeline.fix_git import SubprocessFixGit


class FakeFixGit(SubprocessFixGit):
    """Reads real git except where a replacement is given."""

    def __init__(
        self,
        *,
        branch: Callable[[str], str] | None = None,
        head: Callable[[str], str | None] | None = None,
        changed: Callable[[str], list[str] | str] | None = None,
    ) -> None:
        self._branch = branch
        self._head = head
        self._changed = changed

    def current_branch(self, cwd: str) -> str:
        return self._branch(cwd) if self._branch else super().current_branch(cwd)

    def head(self, cwd: str) -> str | None:
        return self._head(cwd) if self._head else super().head(cwd)

    def changed_paths(self, cwd: str) -> list[str] | str:
        return self._changed(cwd) if self._changed else super().changed_paths(cwd)
