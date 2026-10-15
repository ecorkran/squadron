"""Tests for building per-action usage records (slice 175 D4–D7)."""

from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import patch

import pytest

from squadron.core.models import Effort
from squadron.core.usage import CostBasis, RunTelemetry, TokenUsage, UsageRecord
from squadron.models.aliases import ModelAlias
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.usage_capture import (
    UsageCapture,
    UsageCaptureMissingError,
    require_capture,
    stamp,
)
from squadron.providers.base import COST_USD_KEY, TURNS_KEY, USAGE_KEY
from squadron.providers.errors import ProviderAPIError
from squadron.review.models import ReviewResult, Verdict

_MOD = "squadron.pipeline.usage_capture"
_PRICED: ModelAlias = {
    "profile": "openrouter",
    "model": "x/priced",
    "pricing": {"input": 1.0, "cache_read": 0.5, "output": 4.0},
}
_PARTIAL: ModelAlias = {"profile": "openrouter", "model": "x/partial", "pricing": {"input": 1.0}}


@pytest.fixture(autouse=True)
def _aliases():  # pyright: ignore[reportUnusedFunction]
    aliases = {"priced": _PRICED, "partial": _PARTIAL}
    with patch("squadron.models.aliases.get_all_aliases", return_value=aliases):
        yield


def _resolved(
    alias: str | None, profile: str = "openrouter", effort: Effort | None = None
) -> ResolvedModel:
    return ResolvedModel("model-id", profile, effort=effort, alias=alias)


def test_sdk_agent_metadata_keeps_provider_cost() -> None:
    metadata: dict[str, object] = {
        TURNS_KEY: 3,
        USAGE_KEY: TokenUsage(prompt=100, cached=60, cache_write=20, completion=9),
        COST_USD_KEY: 0.41,
        "answering_models": ["claude-opus-x"],
    }

    record = UsageCapture(set()).record_from_message(
        _resolved("priced", "sdk"), metadata, started=0.0, model="req", effort_sent=None
    )

    assert record is not None
    assert (record.cost_usd, record.cost_basis) == (0.41, CostBasis.PROVIDER)
    assert record.model == "claude-opus-x"
    assert record.turns == 3


def test_openai_metadata_priced_from_alias() -> None:
    metadata: dict[str, object] = {
        TURNS_KEY: 2,
        USAGE_KEY: TokenUsage(prompt=1000, cached=400, completion=10),
    }

    record = UsageCapture(set()).record_from_message(
        _resolved("priced"), metadata, started=0.0, model="m", effort_sent=Effort.low
    )

    assert record is not None
    assert record.cost_basis is CostBasis.ALIAS_PRICING
    assert record.cost_usd == pytest.approx(600 / 1e6 * 1.0 + 400 / 1e6 * 0.5 + 10 / 1e6 * 4.0)
    assert record.effort == "low"


def test_codex_metadata_records_one_turn() -> None:
    metadata: dict[str, object] = {TURNS_KEY: 1, USAGE_KEY: TokenUsage(prompt=10, completion=2)}

    record = UsageCapture(set()).record_from_message(
        _resolved(None, "openai-oauth"), metadata, started=0.0, model="codex", effort_sent=None
    )

    assert record is not None and record.turns == 1


def test_session_telemetry_record() -> None:
    telemetry = RunTelemetry(turns=4, usage=TokenUsage(prompt=50, completion=5), cost_usd=0.02)

    record = UsageCapture(set()).record_from_telemetry(
        _resolved("priced", "sdk"), telemetry, started=0.0, model="m", effort_sent=None
    )

    assert record is not None
    assert (record.turns, record.cost_usd, record.cost_basis) == (4, 0.02, CostBasis.PROVIDER)


def test_provider_error_telemetry_record() -> None:
    exc = ProviderAPIError("boom")
    exc.telemetry = RunTelemetry(turns=1, usage=TokenUsage(prompt=1000, completion=10))
    exc.duration_seconds = 7.5

    record = UsageCapture(set()).record_from_error(
        _resolved("priced"), exc, model="m", effort_sent=None
    )

    assert record is not None
    assert record.duration_seconds == 7.5
    assert record.cost_basis is CostBasis.ALIAS_PRICING


def test_error_without_telemetry_records_nothing() -> None:
    capture = UsageCapture(set())

    assert (
        capture.record_from_error(
            _resolved("priced"), ProviderAPIError("x"), model="m", effort_sent=None
        )
        is None
    )


def test_bare_model_id_keeps_provider_cost_and_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    metadata: dict[str, object] = {USAGE_KEY: TokenUsage(prompt=5, completion=1), COST_USD_KEY: 0.01}

    with caplog.at_level(logging.WARNING):
        record = UsageCapture(set()).record_from_message(
            _resolved(None, "sdk"), metadata, started=0.0, model="m", effort_sent=None
        )

    assert record is not None
    assert record.alias is None
    assert record.cost_usd == 0.01
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_partial_record_sets_flag_and_warns_with_run_and_step(caplog: pytest.LogCaptureFixture) -> None:
    telemetry = RunTelemetry(turns=1, usage=TokenUsage(prompt=5, completion=1))

    with caplog.at_level(logging.WARNING, logger=_MOD):
        record = UsageCapture(set()).record_from_telemetry(
            _resolved(None, "sdk"),
            telemetry,
            started=0.0,
            model="m",
            effort_sent=None,
            partial=True,
            run_id="run-abc",
            step_name="design",
        )

    assert record is not None and record.partial
    message = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert "interrupt drained no result" in message
    assert "run-abc" in message and "design" in message


def _partially_priced() -> dict[str, object]:
    return {USAGE_KEY: TokenUsage(prompt=10, completion=5)}  # no output price on "partial"


def test_pricing_warning_once_per_capture(caplog: pytest.LogCaptureFixture) -> None:
    first = UsageCapture(set())
    with caplog.at_level(logging.WARNING, logger="squadron.models.aliases"):
        for _ in range(2):
            first.record_from_message(
                _resolved("partial"), _partially_priced(), started=0.0, model="m", effort_sent=None
            )
        UsageCapture(set()).record_from_message(
            _resolved("partial"), _partially_priced(), started=0.0, model="m", effort_sent=None
        )

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


def test_duration_is_the_monotonic_delta() -> None:
    telemetry = RunTelemetry(turns=1, usage=TokenUsage(prompt=1, completion=1))

    with patch(f"{_MOD}.time.monotonic", return_value=112.5):
        record = UsageCapture(set()).record_from_telemetry(
            _resolved(None), telemetry, started=100.0, model="m", effort_sent=None
        )

    assert record is not None and record.duration_seconds == pytest.approx(12.5)


def test_nothing_reported_records_nothing_and_stamp_skips() -> None:
    record = UsageCapture(set()).record_from_telemetry(
        _resolved(None), RunTelemetry(), started=0.0, model="m", effort_sent=None
    )
    metadata: dict[str, object] = {}

    stamp(metadata, record)

    assert record is None
    assert USAGE_KEY not in metadata


def test_stamp_writes_persisted_shape() -> None:
    record = UsageRecord(
        model="m",
        alias=None,
        profile="sdk",
        effort=None,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(prompt=1),
        cost_usd=None,
        cost_basis=None,
    )
    metadata: dict[str, object] = {}

    stamp(metadata, record)

    assert metadata[USAGE_KEY] == record.to_dict()


def test_effort_gap_logged_once_per_capture(caplog: pytest.LogCaptureFixture) -> None:
    capture = UsageCapture(set())
    resolved = _resolved("priced", "sdk", effort=Effort.high)

    with caplog.at_level(logging.DEBUG, logger=_MOD):
        assert capture.effort_for_session(resolved) is None
        assert capture.effort_for_session(resolved) is None

    assert len([r for r in caplog.records if "#216" in r.getMessage()]) == 1


def test_review_record_reuses_review_duration_and_cost() -> None:
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="ok",
        template_name="code",
        input_files={},
        timestamp=datetime(2026, 10, 14),
        model="answered",
        turns=2,
        usage=TokenUsage(prompt=10, completion=2),
        duration_seconds=33.0,
        cost_usd=0.5,
        cost_basis=CostBasis.PROVIDER,
    )

    record = UsageCapture(set()).record_from_review(result, _resolved("priced", "sdk"), Effort.low)

    assert record is not None
    assert (record.duration_seconds, record.cost_usd, record.cost_basis) == (
        33.0,
        0.5,
        CostBasis.PROVIDER,
    )
    assert (record.model, record.effort) == ("answered", "low")


def test_require_capture_names_the_action() -> None:
    with pytest.raises(UsageCaptureMissingError, match="dispatch"):
        require_capture(None, "dispatch")


@pytest.mark.asyncio
async def test_executor_gives_every_step_one_capture(caplog: pytest.LogCaptureFixture) -> None:
    from unittest.mock import MagicMock

    from squadron.pipeline.executor import execute_pipeline
    from squadron.pipeline.models import ActionContext, ActionResult
    from squadron.pipeline.steps import register_step_type
    from tests.pipeline.test_executor import make_pipeline, make_step_config, mock_step_type

    seen: list[UsageCapture | None] = []

    class _Recorder:
        async def execute(self, context: ActionContext) -> ActionResult:
            seen.append(context.usage_capture)
            capture = require_capture(context.usage_capture, "dispatch")
            capture.record_from_message(
                _resolved("partial"), _partially_priced(), started=0.0, model="m", effort_sent=None
            )
            return ActionResult(success=True, action_type="dispatch", outputs={})

    register_step_type("_test_usage_capture", mock_step_type([("dispatch", {})]))
    pipeline = make_pipeline(
        [
            make_step_config("_test_usage_capture", "one", {}),
            make_step_config("_test_usage_capture", "two", {}),
        ]
    )

    with caplog.at_level(logging.WARNING, logger="squadron.models.aliases"):
        await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"dispatch": _Recorder()},
        )

    assert len(seen) == 2 and seen[0] is not None and seen[0] is seen[1]
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
