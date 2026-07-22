"""Pydantic records at the metrology file boundary.

These are the shapes persisted to and read from the metrology store. Value
objects that participate in identity (``ProjectId``, ``JudgeResultRef``,
``JudgeConfigId``) live here so both ``identity.py`` (which derives them) and
``store.py`` (which persists them) depend on one definition.

This module is grown across the slice's tasks: T2 lands ``ProjectId``; T4
adds the reference/config-id models; T6 adds ``SampleVerdict`` and the
``MetrologyRecord`` envelope.
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
