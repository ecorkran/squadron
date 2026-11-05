"""A replay config's identity and the label a report row shows for it (slice 420 D6).

A config is what went on the wire: model, profile, effort sent, ``tool_use`` and
``max_output_tokens``. The alias is a display name, so two aliases that sent the same
thing are one config and their row names both.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple


class ConfigIdentity(NamedTuple):
    """The fields of a producer config that decide which report row it belongs to."""

    model: str
    profile: str | None
    effort_sent: str | None
    tool_use: bool | None
    max_output_tokens: int | None


def config_label(identity: ConfigIdentity, aliases: Sequence[str]) -> str:
    """The row key as text: the alias names, then the identity.

    ``tool_use`` and ``max_output_tokens`` appear only when they depart from the default,
    so a plain config reads as it did before they were part of the identity.
    """
    parts = [
        identity.model,
        identity.profile or "no profile",
        f"effort {identity.effort_sent or 'none'}",
    ]
    if identity.tool_use is False:
        parts.append("tools off")
    if identity.max_output_tokens is not None:
        parts.append(f"max {identity.max_output_tokens} output tokens")
    return f"{', '.join(sorted(set(aliases)))} ({', '.join(parts)})"
