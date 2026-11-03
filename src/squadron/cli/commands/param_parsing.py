"""Shared ``--param key=value`` parsing for the commands that take ``-p``."""

from __future__ import annotations

import typer


def param_pairs(param_list: list[str] | None) -> list[tuple[str, str]]:
    """Split ``--param`` entries into (key, value) pairs.

    One entry may hold several comma-separated pairs (``-p a=1,b=2``, #207). A pair
    with no key or no ``=`` is an error, never a silently empty value.
    """
    pairs: list[tuple[str, str]] = []
    for entry in param_list or []:
        for pair in entry.split(","):
            key, sep, value = pair.partition("=")
            if not key.strip() or not sep:
                raise typer.BadParameter(
                    f"Invalid --param '{pair.strip()}' in '{entry}': expected key=value"
                )
            pairs.append((key.strip(), value.strip()))
    return pairs
