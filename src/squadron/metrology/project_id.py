"""The metrology project identity value object.

Lives apart from ``models.py`` so ``replay_models.py`` can depend on it while
``models.py`` depends on ``replay_models.py`` for the envelope's sibling fields.
``models.py`` re-exports both names, so existing imports are unchanged.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ProjectIdSource(StrEnum):
    """Where a ``ProjectId``'s canonical value came from.

    ``remote`` — derived from the git remote URL.
    ``recorded`` — read from ``.squadron.toml`` (``metrology.project_id``).
    """

    REMOTE = "remote"
    RECORDED = "recorded"


class ProjectId(BaseModel):
    """A stable, explicit project identity — never a filesystem path.

    ``value`` is the canonical identity string (git-remote-derived or a
    recorded id). ``source`` marks which it is, so downstream slices can
    reason about identity provenance.
    """

    value: str
    source: ProjectIdSource
