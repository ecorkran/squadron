"""Enums of the benchmark replay records (slice 424 D7, D10): outcome, absence, leak, status."""

from __future__ import annotations

from enum import StrEnum


class ProducerOutcome(StrEnum):
    """How one producer replay ended (slice 424 D10); the values are the table's first column."""

    ENVIRONMENT_FAILED = "environment_failed"
    NO_RUN_STATE = "no_run_state"
    FROZEN_TEXT_MISMATCH = "frozen_text_mismatch"
    COST_CAP = "cost_cap"
    BLOCKED = "blocked"
    COMMITTED = "committed"
    NO_COMMIT = "no_commit"
    PRODUCER_FAILED = "producer_failed"


class AbsenceClass(StrEnum):
    """Why a replay has no usable artifact. A ``committed`` replay has none (``None``)."""

    HARNESS = "harness"
    CONFIG = "config"


class LeakVerdict(StrEnum):
    LEAKED = "leaked"
    NO_LEAK_DETECTED = "no_leak_detected"
    SCAN_UNAVAILABLE = "scan_unavailable"


class LeakRule(StrEnum):
    PATH = "path"
    GIT_OR_HOST = "git_or_host"
    OWN_PACKAGE = "own_package"


class BenchmarkStatus(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"
