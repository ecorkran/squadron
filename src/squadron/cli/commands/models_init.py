"""Starter ``models.toml`` text for ``sq models init`` (slice 940 D2)."""

from __future__ import annotations

from pathlib import Path

_COMMENT_PREFIX = "#"

_HEADER = """\
# Squadron model aliases — your file, ~/.config/squadron/models.toml.
# Everything below is commented out, so this file defines nothing yet.
# Uncomment and edit an entry to add an alias; your aliases extend and
# override the built-in ones.
#
# Reference, copied from the built-in models.toml:
#
"""

_EXAMPLES = """\
#
# Example alias:
#
# [aliases.my-alias]
# profile = "openrouter"
# model = "provider/model-id"
#
# Example variant of that alias with a reasoning effort:
#
# [aliases.my-alias-low]
# profile = "openrouter"
# model = "provider/model-id"
# effort = "low"
"""


def leading_comment_block(text: str) -> str:
    """Lines from the first line up to the first one that does not start with ``#``."""
    block: list[str] = []
    for line in text.splitlines():
        if not line.startswith(_COMMENT_PREFIX):
            break
        block.append(line)
    return "\n".join(block)


def build_starter_text(builtin_text: str, *, source: Path) -> str:
    """The commented-out starter file: a header, the built-in reference, two examples.

    Raises ``ValueError`` naming *source* when its leading comment block is empty:
    a starter without the reference would be a file that teaches nothing.
    """
    reference = leading_comment_block(builtin_text)
    if not reference:
        raise ValueError(f"{source} does not open with a comment block; no reference to copy")
    return f"{_HEADER}{reference}\n{_EXAMPLES}"
