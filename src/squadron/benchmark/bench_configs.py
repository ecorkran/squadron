"""Model aliases as benchmark configs (slice 424 Task 32).

One place turns an alias into the two shapes the runner needs: the ``BenchConfig`` that
identifies it in the plan, and the ``ProducerConfigRef`` stored on records. An unknown alias
refuses naming it.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.benchmark.bench_plan import BenchConfig, BenchmarkRefusal
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.models.aliases import (
    ModelAlias,
    get_all_aliases,
    model_allows_tools,
    model_effort,
    model_max_output_tokens,
)
from squadron.pipeline.usage_capture import output_budget_sent_by_profile
from squadron.providers.base import ProfileName


def _entry(alias: str) -> ModelAlias:
    known = get_all_aliases()
    if alias not in known:
        raise BenchmarkRefusal(f"unknown model alias '{alias}'")
    return known[alias]


def bench_config(alias: str) -> BenchConfig:
    """The plan's identity for *alias*: its model, profile and configured effort."""
    entry = _entry(alias)
    effort = model_effort(alias)
    return BenchConfig(
        alias=alias,
        model=entry["model"],
        profile=entry["profile"],
        effort_configured=None if effort is None else effort.value,
    )


def producer_config_ref(alias: str) -> ProducerConfigRef:
    """The record's config reference; ``effort_sent`` is filled from the run's own usage."""
    entry = _entry(alias)
    profile = entry["profile"]
    return ProducerConfigRef(
        alias=alias,
        model=entry["model"],
        profile=profile,
        effort_sent=None,
        # Through the alias readers, never the raw field: absence of ``tool_use`` means allow.
        tool_use=model_allows_tools(alias),
        # Recorded as sent: only a provider that applies the budget puts it on the wire.
        max_output_tokens=output_budget_sent_by_profile(profile, model_max_output_tokens(alias)),
    )


def aliases_without_cost(aliases: Sequence[str]) -> frozenset[str]:
    """Aliases whose replays report no cost: not the SDK (provider-reported) and unpriced.

    The SDK reports its own cost; every other profile is priced from the alias's pricing
    table (``resolve_cost``), so an alias with none reports nothing.
    """
    return frozenset(
        alias
        for alias in aliases
        if (entry := _entry(alias))["profile"] != ProfileName.SDK.value and entry.get("pricing") is None
    )
