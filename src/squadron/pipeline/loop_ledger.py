"""The commit ledger of a planning review loop (slice 202).

A ``commit_each_iteration`` loop records the shas of the commits it makes, plus the
phase commit made just before it, so that on completion it can replace exactly those
commits with one. The ledger lives on ``StepResult`` and ``StepState`` so a pause
carries it across a resume.

This module must not import ``executor`` at module level: the executor imports it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoopCommitLedger(BaseModel):
    """The commits a loop made, oldest first, and the sha they sit on."""

    base_sha: str
    commits: list[str] = Field(default_factory=lambda: [])
    # True when the loop cannot prove which commits are its own; collapse then refuses.
    unprovable: bool = False
