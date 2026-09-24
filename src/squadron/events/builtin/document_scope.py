"""cf's user-document root, defined once for every COMMIT gate that scopes by it."""

from __future__ import annotations

from pathlib import Path

CF_DOCUMENT_ROOT = ("project-documents", "user")


def is_under_cf_document_root(staged_path: str, cwd: str) -> bool:
    """Is `staged_path` under cf's user-document root in the repo at `cwd`?

    Paths are resolved against `cwd` and compared by parts, so a repo-relative,
    `./`-prefixed, or absolute spelling of the same file classifies identically
    (#122). A path that resolves outside `cwd` is out of scope.
    """
    repo_root = Path(cwd).resolve()
    try:
        relative = (repo_root / staged_path).resolve().relative_to(repo_root)
    except ValueError:
        # Resolves outside the repo: cannot be under its document root.
        return False
    return relative.parts[: len(CF_DOCUMENT_ROOT)] == CF_DOCUMENT_ROOT
