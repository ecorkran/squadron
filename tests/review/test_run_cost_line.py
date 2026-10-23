"""The terminal usage line: printed for every review, saved or not (#259)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from squadron.cli.commands.review import (
    _display_terminal,  # pyright: ignore[reportPrivateUsage]
)
from squadron.core.usage import CostBasis, TokenUsage
from squadron.providers.errors import ProviderError
from squadron.review.models import ReviewResult, Verdict
from squadron.review.run_cost import COST_NOT_REPORTED, NOT_COMPUTED, RunCost


def _terminal_text(result: ReviewResult, verbosity: int = 0) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    with patch("squadron.cli.commands.review.Console", return_value=console):
        _display_terminal(result, verbosity)
    return buf.getvalue()


def _result(**overrides: object) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="",
        template_name="code",
        input_files={},
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def test_summary_line_reports_tokens_and_priced_cost() -> None:
    cost = RunCost(
        usage=TokenUsage(prompt=1200, cached=800, completion=300),
        cost_usd=0.4123,
        cost_basis=CostBasis.PROVIDER,
    )
    assert cost.summary_line() == (
        "Usage: prompt 1200, cached 800, completion 300 — cost $0.41 (provider)"
    )


def test_summary_line_never_turns_unreported_into_zero() -> None:
    line = RunCost().summary_line()
    assert NOT_COMPUTED in line
    assert COST_NOT_REPORTED in line
    assert "0" not in line


def test_terminal_output_prints_usage_line_at_default_verbosity() -> None:
    result = _result(cost_usd=0.02, usage=TokenUsage(prompt=10, cached=0, completion=5))
    assert "Usage: prompt 10, cached 0, completion 5 — cost $0.02" in _terminal_text(result)


def test_failed_run_summary_carries_the_cost_before_the_error() -> None:
    exc = ProviderError("boom")
    exc.cost_usd = 0.005
    exc.cost_basis = CostBasis.ALIAS_PRICING
    line = RunCost.from_error(exc).summary_line()
    assert "cost $0.0050 (alias_pricing)" in line
