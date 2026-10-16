"""Prompt identity for dispatch metadata (slice 177 D8).

A dispatch records which prompt it delivered (a hash of the final text), which
branch of ``_resolve_prompt`` produced it, and the tool versions that composed it,
so producer-effectiveness reports can say how much of their data is identified.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

import squadron

#: ``ActionResult.metadata`` key holding the identity dict.
PROMPT_METADATA_KEY = "prompt"


class PromptSource(StrEnum):
    """The ``_resolve_prompt`` branch that produced the delivered prompt."""

    BUILD_CONTEXT = "build_context"
    FEEDBACK = "feedback"
    EXPLICIT = "explicit"
    REVIEW_FINDINGS = "review_findings"


@dataclass(frozen=True)
class ResolvedPrompt:
    """The delivered prompt text and where it came from.

    ``cf_version`` and ``guide_version`` are copied from the ``build_context``
    result and are ``None`` for every other source.
    """

    text: str
    source: PromptSource
    cf_version: str | None = None
    guide_version: str | None = None

    def identity(self) -> dict[str, object]:
        """The D8 ``metadata["prompt"]`` value."""
        return {
            "sha256": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "source": self.source.value,
            "squadron_version": squadron.__version__,
            "cf_version": self.cf_version,
            "guide_version": self.guide_version,
        }
