"""The record of one file whose text went into a review prompt (#382).

A leaf module: ``review.models`` carries these on a result, so it imports nothing from
the review package.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = ["InjectedFile", "injected_file"]


@dataclass(frozen=True)
class InjectedFile:
    """One file whose text went into the review prompt, as proof of what the model was given."""

    key: str
    path: str
    chars: int
    sha256: str
    #: False when the text was cut to a size cap before injection.
    whole: bool


def injected_file(key: str, path: str, content: str, *, injected_chars: int) -> InjectedFile:
    """The record for *content* of *path*, of which *injected_chars* reached the prompt."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return InjectedFile(key, path, len(content), digest, whole=injected_chars >= len(content))
