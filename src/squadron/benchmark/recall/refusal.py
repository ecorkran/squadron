"""The one refusal type of ``sq benchmark recall`` commands (slice 430)."""

from __future__ import annotations


class RecallRefusal(ValueError):
    """A recall command refuses; reported as ``Error: <message>`` with exit 1."""
