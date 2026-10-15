"""Tests for ``price_usage`` and ``resolve_cost`` (slice 175 D3)."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from squadron.core.usage import CostBasis, TokenUsage
from squadron.models.aliases import ModelAlias, price_usage, resolve_cost

_PRICED: ModelAlias = {
    "profile": "openrouter",
    "model": "x/full",
    "pricing": {"input": 2.0, "cache_read": 0.5, "cache_write": 2.5, "output": 8.0},
}
_NO_CACHE_WRITE_PRICE: ModelAlias = {
    "profile": "openrouter",
    "model": "x/partial",
    "pricing": {"input": 2.0, "cache_read": 0.5, "output": 8.0},
}
_UNPRICED: ModelAlias = {"profile": "sdk", "model": "claude-x"}
_ALIASES = {"full": _PRICED, "partial": _NO_CACHE_WRITE_PRICE, "sub": _UNPRICED}


@pytest.fixture(autouse=True)
def _aliases():  # pyright: ignore[reportUnusedFunction]
    with patch("squadron.models.aliases.get_all_aliases", return_value=_ALIASES):
        yield


def _per_million(count: int, price: float) -> float:
    return count / 1_000_000 * price


def test_full_pricing_sums_each_class() -> None:
    usage = TokenUsage(prompt=1_000, cached=600, cache_write=100, completion=50)

    cost = price_usage("full", usage, set())

    expected = (
        _per_million(300, 2.0) + _per_million(600, 0.5) + _per_million(100, 2.5) + _per_million(50, 8.0)
    )
    assert cost == pytest.approx(expected)


def test_no_cache_tokens_prices_input_and_output() -> None:
    usage = TokenUsage(prompt=1_000, completion=50)

    assert price_usage("partial", usage, set()) == pytest.approx(
        _per_million(1_000, 2.0) + _per_million(50, 8.0)
    )


def test_missing_class_price_returns_none_and_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    usage = TokenUsage(prompt=1_000, cache_write=10, completion=5)
    warned: set[str] = set()

    with caplog.at_level(logging.WARNING, logger="squadron.models.aliases"):
        assert price_usage("partial", usage, warned) is None
        assert price_usage("partial", usage, warned) is None

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "partial" in warnings[0] and "cache_write" in warnings[0]


def test_inconsistent_counts_return_none_and_warn(caplog: pytest.LogCaptureFixture) -> None:
    usage = TokenUsage(prompt=100, cached=90, cache_write=20, completion=5)

    with caplog.at_level(logging.WARNING, logger="squadron.models.aliases"):
        assert price_usage("full", usage, set()) is None

    assert any("full" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


@pytest.mark.parametrize("alias", ["sub", "unknown", None])
def test_unpriced_or_unknown_alias_returns_none_silently(
    alias: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.models.aliases"):
        assert price_usage(alias, TokenUsage(prompt=10, completion=1), set()) is None

    assert not caplog.records


def test_missing_prompt_or_completion_returns_none() -> None:
    assert price_usage("full", TokenUsage(completion=1), set()) is None
    assert price_usage("full", TokenUsage(prompt=1), set()) is None


def test_resolve_cost_provider_wins() -> None:
    usage = TokenUsage(prompt=1_000, completion=50)

    assert resolve_cost("full", usage, 0.42, set()) == (0.42, CostBasis.PROVIDER)


def test_resolve_cost_falls_back_to_alias_pricing() -> None:
    cost, basis = resolve_cost("full", TokenUsage(prompt=1_000, completion=50), None, set())

    assert basis is CostBasis.ALIAS_PRICING
    assert cost == pytest.approx(_per_million(1_000, 2.0) + _per_million(50, 8.0))


def test_resolve_cost_none_when_neither() -> None:
    assert resolve_cost("sub", TokenUsage(prompt=1, completion=1), None, set()) == (None, None)


def test_resolve_cost_keeps_reported_zero() -> None:
    assert resolve_cost("full", TokenUsage(), 0.0, set()) == (0.0, CostBasis.PROVIDER)
