"""Errors that stop a fix-case build (slice 422)."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class BuildHalted(Exception):
    """The build cannot continue; the reason is in the message.

    Raised only after an ERROR log, so the stop is observable wherever the caller
    reports it. Never used for a candidate-level failure: those are recorded as a
    rejection or a ``harness_error`` and the build moves on.
    """


def halt(message: str) -> BuildHalted:
    """Log ``message`` at ERROR and return the ``BuildHalted`` to raise."""
    _logger.error(message)
    return BuildHalted(message)
