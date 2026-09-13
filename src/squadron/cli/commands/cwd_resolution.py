"""Shared working-directory resolution for CLI commands.

``sq review code`` and ``sq pr show`` both anchor at the git root: an agent's
``cwd`` is its tool jail root, so a config ``cwd`` pointing at a subdirectory of
the repo makes every repo-relative path unreadable. This module holds that
resolution once so both commands resolve identically.

``metrology.py`` has its own, deliberately different ``_resolve_cwd`` that
ignores the ``cwd`` config key — that key scopes review document lookups inside
``project-documents/user``, which is the wrong root for metrology. It changes
for different reasons and is not folded in here.

The ``cli -> review`` import of ``find_git_root`` is an existing and permitted
direction. Modules under ``codehost/`` must not acquire it in either direction;
the import-graph test pins ``cli -> codehost -> core``.
"""

from __future__ import annotations

from squadron.review.git_utils import find_git_root


def resolve_cwd(cwd: str | None) -> str:
    """Resolve the working directory: CLI flag overrides config default.

    ``get_config`` is reached through :mod:`squadron.cli.commands.review` at
    call time rather than imported here. Nine test files fake the config by
    patching ``squadron.cli.commands.review.get_config``, and that seam covers
    every config key the review command reads; resolving through it keeps the
    cwd path on the established patch point instead of splitting the seam
    across two module paths. The import is function-local because ``review``
    imports this module.
    """
    if cwd is not None:
        return cwd
    from squadron.cli.commands import review

    config_val = review.get_config("cwd")
    if isinstance(config_val, str):
        return config_val
    return "."


def resolve_repo_cwd(cwd: str | None) -> str:
    """Resolve ``cwd`` and anchor it at the containing git root.

    Falls back to the resolved cwd when there is no git work tree (issue #86).
    """
    resolved_cwd = resolve_cwd(cwd)
    return find_git_root(resolved_cwd) or resolved_cwd
