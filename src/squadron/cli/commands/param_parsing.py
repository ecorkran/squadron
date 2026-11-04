"""Shared ``--param key=value`` parsing for the commands that take ``-p``."""

from __future__ import annotations

import click
import typer
from typer.core import TyperCommand


def param_pairs(param_list: list[str] | None) -> list[tuple[str, str]]:
    """Split ``--param`` entries into (key, value) pairs.

    One entry may hold several comma-separated pairs (``-p a=1,b=2``, #207). A pair
    with no key or no ``=`` is an error, never a silently empty value. A single trailing
    comma is dropped (``-p a=1, b=2`` reaches here as ``a=1,``); ``a=1,,b=2`` still errors.
    """
    pairs: list[tuple[str, str]] = []
    for entry in param_list or []:
        for pair in entry.rstrip().removesuffix(",").split(","):
            key, sep, value = pair.partition("=")
            if not key.strip() or not sep:
                raise typer.BadParameter(
                    f"Invalid --param '{pair.strip()}' in '{entry}': expected key=value"
                )
            pairs.append((key.strip(), value.strip()))
    return pairs


def with_stray_pairs(param_list: list[str] | None, extra_args: list[str]) -> list[str] | None:
    """Fold stray ``key=value`` arguments into *param_list*.

    ``-p a=1, b=2`` reaches the CLI as ``-p "a=1,"`` plus a bare ``b=2``; the bare
    one is the second param. Any extra argument that is not ``key=value`` is an error.
    """
    for extra in extra_args:
        if "=" not in extra:
            raise typer.BadParameter(f"Unexpected extra argument '{extra}'")
    if not extra_args:
        return param_list
    return [*(param_list or []), *extra_args]


class StrayParamCommand(TyperCommand):
    """A command whose stray ``key=value`` arguments count as ``-p`` params (#291)."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        remaining = super().parse_args(ctx, args)
        ctx.params["param"] = with_stray_pairs(ctx.params.get("param"), ctx.args)
        ctx.args = []
        return remaining
