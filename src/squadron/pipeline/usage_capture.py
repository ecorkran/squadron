"""Building per-action ``UsageRecord``s (slice 175 D4–D7).

The one place a ``UsageRecord`` is built. Providers report what they measured (tokens,
turns, cost) on message metadata or session telemetry; this module attributes it to the
alias and profile that ran, measures the call's duration, and resolves the cost (D3).
Actions only call it and ``stamp`` the result into ``ActionResult.metadata``.

One ``UsageCapture`` per run, created by the executor. It holds only the run's
pricing-warning set and the D7 logged flag, and catches nothing: a cancelled action
propagates unchanged and records nothing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping

from squadron.core.models import Effort
from squadron.core.usage import RunTelemetry, TokenUsage, UsageRecord
from squadron.models.aliases import resolve_cost
from squadron.pipeline.resolver import ResolvedModel
from squadron.providers.base import COST_USD_KEY, TURNS_KEY, USAGE_KEY
from squadron.providers.errors import ProviderError
from squadron.providers.loader import ensure_provider_loaded
from squadron.providers.profiles import get_profile
from squadron.providers.registry import get_provider
from squadron.review.models import ReviewResult

_logger = logging.getLogger(__name__)

#: Message-metadata keys a one-shot caller copies for ``record_from_message``.
USAGE_METADATA_KEYS = (TURNS_KEY, USAGE_KEY, COST_USD_KEY, "answering_models")


def copy_usage_metadata(metadata: Mapping[str, object], into: dict[str, object]) -> None:
    """Copy the usage keys a response stamped into ``into``; a later stamp wins."""
    for key in USAGE_METADATA_KEYS:
        value = metadata.get(key)
        if value is not None:
            into[key] = value


#: The ``usage_metadata`` key a one-shot runner sets to the effort it actually sent.
EFFORT_SENT_KEY = "effort_sent"


def note_effort_sent(
    usage_metadata: dict[str, object] | None, effort: Effort | None, applies_effort: bool
) -> None:
    """Record the effort a one-shot agent sends: the alias value only if applied (D7)."""
    if usage_metadata is not None:
        usage_metadata[EFFORT_SENT_KEY] = effort if applies_effort else None


def effort_sent_by_profile(profile_name: str, effort: Effort | None) -> Effort | None:
    """The effort a call on ``profile_name`` sends: the alias value only if applied (D7).

    For paths that have no ``usage_metadata`` to read it from (a failed review).
    """
    provider = get_profile(profile_name).provider
    ensure_provider_loaded(provider)
    return effort if get_provider(provider).capabilities.applies_effort else None


def read_effort_sent(usage_metadata: Mapping[str, object]) -> Effort | None:
    """The effort ``note_effort_sent`` recorded; ``None`` when none was sent."""
    value = usage_metadata.get(EFFORT_SENT_KEY)
    return value if isinstance(value, Effort) else None


class UsageCapture:
    """Builds usage records for one run's LLM actions."""

    def __init__(self, warned: set[str]) -> None:
        self._warned = warned
        self._effort_gap_logged = False

    def record_from_message(
        self,
        resolved: ResolvedModel | None,
        message_metadata: Mapping[str, object],
        *,
        started: float,
        model: str | None,
        effort_sent: Effort | None,
    ) -> UsageRecord | None:
        """A record from what an ``Agent`` stamped on its final message."""
        usage = message_metadata.get(USAGE_KEY)
        turns = message_metadata.get(TURNS_KEY)
        cost = message_metadata.get(COST_USD_KEY)
        answering = message_metadata.get("answering_models")
        if isinstance(answering, list) and answering:
            model = str(answering[-1])  # pyright: ignore[reportUnknownArgumentType]
        return self._build(
            resolved,
            model=model,
            effort=effort_sent,
            turns=turns if isinstance(turns, int) else None,
            duration=time.monotonic() - started,
            usage=usage if isinstance(usage, TokenUsage) else None,
            provider_cost=cost if isinstance(cost, float | int) else None,
        )

    def record_from_telemetry(
        self,
        resolved: ResolvedModel | None,
        telemetry: RunTelemetry,
        *,
        started: float,
        model: str | None,
        effort_sent: Effort | None,
        partial: bool = False,
        run_id: str = "",
        step_name: str = "",
    ) -> UsageRecord | None:
        """A record from session telemetry or a ``ProviderError``'s telemetry."""
        if partial:
            _logger.warning(
                "SDK session interrupt drained no result; spend for the interrupted turn "
                "is not recorded (run %s, step %s)",
                run_id,
                step_name,
            )
        return self._build(
            resolved,
            model=model,
            effort=effort_sent,
            turns=telemetry.turns,
            duration=time.monotonic() - started,
            usage=telemetry.usage,
            provider_cost=telemetry.cost_usd,
            partial=partial,
        )

    def record_from_review(
        self, result: ReviewResult, resolved: ResolvedModel, effort_sent: Effort | None
    ) -> UsageRecord | None:
        """A record from a finished review, reusing its resolved cost and duration."""
        if result.turns is None and not result.usage.reported and result.cost_usd is None:
            return None
        return UsageRecord(
            model=result.model,
            alias=resolved.alias,
            profile=resolved.profile,
            effort=None if effort_sent is None else effort_sent.value,
            turns=result.turns,
            duration_seconds=result.duration_seconds,
            usage=result.usage,
            cost_usd=result.cost_usd,
            cost_basis=result.cost_basis,
        )

    def record_from_error(
        self,
        resolved: ResolvedModel | None,
        exc: ProviderError,
        *,
        model: str | None,
        effort_sent: Effort | None,
    ) -> UsageRecord | None:
        """A record from a failed review: telemetry and duration ride the error."""
        telemetry = exc.telemetry
        if telemetry is None:
            return None
        return self._build(
            resolved,
            model=model,
            effort=effort_sent,
            turns=telemetry.turns,
            duration=exc.duration_seconds,
            usage=telemetry.usage,
            provider_cost=telemetry.cost_usd,
        )

    def effort_for_session(self, resolved: ResolvedModel | None) -> None:
        """The effort the SDK session path sends: none (D7, #216); log the gap once."""
        if resolved is not None and resolved.effort is not None and not self._effort_gap_logged:
            self._effort_gap_logged = True
            _logger.debug(
                "SDK session path does not apply alias effort %s; records show effort not sent (#216)",
                resolved.effort.value,
            )

    def _build(
        self,
        resolved: ResolvedModel | None,
        *,
        model: str | None,
        effort: Effort | None,
        turns: int | None,
        duration: float | None,
        usage: TokenUsage | None,
        provider_cost: float | None,
        partial: bool = False,
    ) -> UsageRecord | None:
        tokens = usage if usage is not None else TokenUsage()
        if not turns and not tokens.reported and provider_cost is None:
            return None
        alias = None if resolved is None else resolved.alias
        cost, basis = resolve_cost(alias, tokens, provider_cost, self._warned)
        return UsageRecord(
            model=model,
            alias=alias,
            profile=None if resolved is None else resolved.profile,
            effort=None if effort is None else effort.value,
            turns=turns,
            duration_seconds=duration,
            usage=tokens,
            cost_usd=cost,
            cost_basis=basis,
            partial=partial,
        )


class UsageCaptureMissingError(RuntimeError):
    """An LLM action ran in a context the executor did not give a ``UsageCapture``."""


def require_capture(capture: UsageCapture | None, action: str) -> UsageCapture:
    """The context's capture; an LLM action never runs without one (Task 16)."""
    if capture is None:
        raise UsageCaptureMissingError(
            f"{action} action has no usage capture: ActionContext.usage_capture must be "
            "set by the executor for every LLM step"
        )
    return capture


def stamp(metadata: dict[str, object], record: UsageRecord | None) -> None:
    """Write ``record`` under ``USAGE_KEY``; nothing when there is no record."""
    if record is not None:
        metadata[USAGE_KEY] = record.to_dict()
