"""Lenient parser for comb decision lines (slice 430, Patterns: decisions parser).

A comb answers one ``<finding-id>: KEEP|DROP — reason`` line per finding, but real outputs
vary: ``F3 - KEEP: reason``, ``**F3**: keep``, ``### [FAIL] F3: KEEP. reason``, or the
verdict trailing the line (``### [NOTE] F3: title — DROP``). A line counts only when it
starts (after markdown) with a finding id and carries a word from ``VERDICT_WORDS``; prose
that merely mentions ids is ignored. The first verdict per id wins; repeats and unknown ids
are counted, never dropped silently. Missing ids become ``UNDECIDED`` (never DROP).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field

from squadron.metrology.recall_run_models import CombDecision, CombVerdict

#: The one word -> verdict table; keys are lower case.
VERDICT_WORDS: dict[str, CombVerdict] = {
    "keep": CombVerdict.KEEP,
    "drop": CombVerdict.DROP,
}

_MARKUP = r"[*_`]*"
_DASH = r"[-–—]"
#: Leading markdown: whitespace, heading/quote/list marks, emphasis, ``[TAG]`` labels.
_LEAD = r"^(?:[\s#>*_`|]|[-+]\s|\d+[.)]\s|\[[^\]]*\])*"
_ID = r"(?P<id>[A-Za-z]{1,3}\d+)\b" + _MARKUP
_VERDICT_FIRST = re.compile(
    _LEAD + _ID + rf"\s*(?:[:.]|{_DASH})?\s*{_MARKUP}(?P<word>[A-Za-z]+)\b(?P<rest>.*)$"
)
_VERDICT_LAST = re.compile(
    _LEAD
    + _ID
    + rf"\s*:?\s*(?P<rest>.*?)\s*(?:{_DASH}|:)\s*{_MARKUP}(?P<word>[A-Za-z]+){_MARKUP}[.!]?\s*$"
)
_REASON_TRIM = re.compile(r"^[\s:.*_`–—-]+|[\s*_]+$")


@dataclass(frozen=True)
class DecisionParse:
    """Decisions per finding id, plus the counts the run record keeps."""

    decisions: dict[str, CombDecision] = field(default_factory=dict[str, CombDecision])
    duplicate_decisions: int = 0
    unknown_ids: int = 0

    @property
    def is_empty(self) -> bool:
        """No decision line at all; the caller records ``config_failure``."""
        return not self.decisions


def parse_decisions(raw: str, finding_ids: Collection[str]) -> DecisionParse:
    """Parse a comb's raw output against the ids it was given."""
    known = set(finding_ids)
    found: dict[str, CombDecision] = {}
    duplicates = 0
    unknown = 0
    any_line = False
    for line in raw.splitlines():
        parsed = _parse_line(line)
        if parsed is None:
            continue
        any_line = True
        finding_id, decision = parsed
        if finding_id not in known:
            unknown += 1
        elif finding_id in found:
            duplicates += 1
        else:
            found[finding_id] = decision
    if not any_line:
        return DecisionParse()
    for finding_id in finding_ids:
        found.setdefault(finding_id, CombDecision(verdict=CombVerdict.UNDECIDED))
    return DecisionParse(decisions=found, duplicate_decisions=duplicates, unknown_ids=unknown)


def _parse_line(line: str) -> tuple[str, CombDecision] | None:
    for pattern in (_VERDICT_FIRST, _VERDICT_LAST):
        match = pattern.match(line)
        if match is None:
            continue
        verdict = VERDICT_WORDS.get(match["word"].lower())
        if verdict is None:
            continue
        reason = _REASON_TRIM.sub("", match["rest"]) or None
        return match["id"].upper(), CombDecision(verdict=verdict, reason=reason)
    return None
