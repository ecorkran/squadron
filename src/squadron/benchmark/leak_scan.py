"""The leak scan: did a producer reach outside its sandbox? (slice 424 D6, D7)

Rules read the tool calls a runtime recorded (``transcripts``) and judge them against
``LeakRules``. The result is ``leaked`` (with the hits), ``no_leak_detected`` or
``scan_unavailable``; an empty or unreadable transcript is never read as clean.

``LEAK_RULES_VERSION`` is recorded on every replay and must be bumped whenever a rule
changes, so replays scanned under different rules are never mistaken for one another.

Known gaps, by design (D7): file access inside scripts the model writes and runs, paths
built at run time, and network reads outside the code host.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from squadron.benchmark.leak_git_package import git_host_hits, own_package_hits
from squadron.benchmark.leak_paths import path_hits
from squadron.benchmark.leak_rules import LeakRules as LeakRules  # re-exported
from squadron.benchmark.leak_rules import build_leak_rules as build_leak_rules  # re-exported
from squadron.benchmark.transcripts import ToolCall, TranscriptSource
from squadron.metrology.benchmark_replay_enums import LeakRule, LeakVerdict
from squadron.metrology.benchmark_replay_models import (
    MAX_LEAK_EXCERPT_CHARS,
    MAX_LEAK_HITS,
    LeakHit,
    LeakScanResult,
)

_logger = logging.getLogger(__name__)

LEAK_RULES_VERSION = 2
#: How many problems the ``scan_unavailable`` detail spells out; the count is always given.
DETAIL_PROBLEMS_SHOWN = 3

#: The rule table: one entry per ``LeakRule``, in the order hits are recorded.
_RULES: tuple[tuple[LeakRule, Callable[[ToolCall, LeakRules], list[str]]], ...] = (
    (LeakRule.PATH, path_hits),
    (LeakRule.GIT_OR_HOST, git_host_hits),
    (LeakRule.OWN_PACKAGE, own_package_hits),
)


def call_hits(call: ToolCall, rules: LeakRules) -> list[LeakHit]:
    """Every rule hit of one tool call; the excerpt is cut explicitly to its limit."""
    return [
        LeakHit(rule=rule, tool=call.tool, excerpt=found[:MAX_LEAK_EXCERPT_CHARS])
        for rule, evaluate in _RULES
        for found in evaluate(call, rules)
    ]


def _result(
    verdict: LeakVerdict, calls_seen: int, hits: tuple[LeakHit, ...], detail: str
) -> LeakScanResult:
    return LeakScanResult(
        verdict=verdict,
        rules_version=LEAK_RULES_VERSION,
        tool_calls_seen=calls_seen,
        hits=hits,
        detail=detail,
    )


def _unavailable(calls_seen: int, detail: str) -> LeakScanResult:
    _logger.warning("leak scan unavailable: %s", detail)
    return _result(LeakVerdict.SCAN_UNAVAILABLE, calls_seen, (), detail)


def scan(source: TranscriptSource, home: Path, rules: LeakRules) -> LeakScanResult:
    """Judge the tool calls recorded under *home*.

    ``leaked`` when any rule hits (the first 20 hits are recorded, the detail says when more
    were found). Otherwise ``scan_unavailable`` when nothing can be trusted as a complete
    read: no transcript file, any line or item the parser could not read, or zero tool calls
    extracted. A transcript with zero calls is never clean: ``turns`` cannot corroborate
    extraction (Codex reports one turn per dispatch), so a replay that did anything at all
    has calls, and none means the parser saw nothing. Only a full read with calls and no hit
    is ``no_leak_detected``.
    """
    transcript = source.read(home)
    calls_seen = len(transcript.tool_calls)
    hits = [hit for call in transcript.tool_calls for hit in call_hits(call, rules)]
    if hits:
        kept = tuple(hits[:MAX_LEAK_HITS])
        more = (
            f"{len(hits)} hits; the first {MAX_LEAK_HITS} are recorded" if len(hits) > len(kept) else ""
        )
        return _result(LeakVerdict.LEAKED, calls_seen, kept, more)
    if transcript.files_read == 0:
        return _unavailable(calls_seen, "; ".join(transcript.problems) or "no transcript file found")
    if transcript.problems:
        shown = "; ".join(transcript.problems[:DETAIL_PROBLEMS_SHOWN])
        return _unavailable(calls_seen, f"{len(transcript.problems)} unreadable items: {shown}")
    if calls_seen == 0:
        return _unavailable(calls_seen, "the transcript holds no tool calls")
    return _result(LeakVerdict.NO_LEAK_DETECTED, calls_seen, (), "")
