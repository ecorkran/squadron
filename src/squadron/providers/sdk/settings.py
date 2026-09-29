"""Declared settings policy for automated SDK paths (slice 932 D9–D11).

With no ``--setting-sources`` flag the CLI loads the operator's user CLAUDE.md
and user settings (output style included), so no automated path may leave
``setting_sources`` unset. Auto-memory loads even under ``project`` and is
controlled separately through ``AUTO_MEMORY_DISABLE_ENV``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, TypedDict

__all__ = [
    "AUTO_MEMORY_DISABLE_ENV",
    "PIPELINE_SETTING_SOURCES",
    "REVIEW_SETTING_SOURCES",
    "SdkSettings",
    "sdk_settings_options",
]

# Pipeline SDK sessions and one-shot SDK dispatch: project conventions only.
PIPELINE_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)
# Reviews and judges (every built-in template, and custom ones that omit the
# key). Same value as the pipeline policy today; kept separate on purpose
# because the two answer different questions and can diverge.
REVIEW_SETTING_SOURCES: Final[tuple[str, ...]] = ("project",)

AUTO_MEMORY_DISABLE_ENV: Final = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"


class SdkSettings(TypedDict):
    """``ClaudeAgentOptions`` kwargs this module decides."""

    setting_sources: list[str]
    env: dict[str, str]


def sdk_settings_options(
    setting_sources: Sequence[str],
    *,
    auto_memory: bool,
    base_env: Mapping[str, str] | None = None,
) -> SdkSettings:
    """Return ``ClaudeAgentOptions`` kwargs for settings sources and auto-memory.

    ``env`` is ``base_env`` merged with the auto-memory disable variable when
    ``auto_memory`` is false. ``base_env`` is never mutated.
    """
    env = dict(base_env or {})
    if not auto_memory:
        env[AUTO_MEMORY_DISABLE_ENV] = "1"
    return {"setting_sources": list(setting_sources), "env": env}
