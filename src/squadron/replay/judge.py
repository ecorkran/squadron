"""The pairwise judge's prompt, verdict parser and order-swap rule (slice 177 D5).

A pair is judged twice with the drafts swapped, so a judge's lean toward the first
position cancels out. Only drafts are compared, with their YAML frontmatter stripped.
"""

from __future__ import annotations

import hashlib
import re

from squadron.data import data_dir
from squadron.metrology.replay_models import JudgeCall, JudgePick, PairOutcome
from squadron.pipeline.text_tail import tail_text

_PROMPT_PATH = ("replay", "pairwise-judge.md")
#: Markdown emphasis and code ticks the judge may wrap its verdict line in.
_EMPHASIS = re.compile(r"[*_`]")
#: ``WINNER: A`` / ``winner = tie``, tolerant of case, spacing, a leading quote or heading
#: mark, and trailing punctuation. The whole line must be the verdict.
_VERDICT_LINE = re.compile(r"^\s*(?:[#>\-]\s*)*winner\s*[:=]\s*(a|b|tie)\s*[.!]?\s*$", re.IGNORECASE)
_FRONTMATTER_DELIMITER = "---"


def judge_prompt() -> str:
    """The packaged judge prompt."""
    return data_dir().joinpath(*_PROMPT_PATH).read_text(encoding="utf-8")


def judge_prompt_hash() -> str:
    """SHA-256 of the packaged prompt; judgments under a different hash are a different judge."""
    return hashlib.sha256(judge_prompt().encode("utf-8")).hexdigest()


def parse_verdict(reply: str) -> JudgeCall:
    """The verdict on the reply's last matching line, else ``INVALID`` with the raw tail."""
    for line in reversed(reply.splitlines()):
        match = _VERDICT_LINE.match(_EMPHASIS.sub("", line))
        if match is not None:
            return JudgeCall(pick=JudgePick(match.group(1).upper()), raw_tail=tail_text(reply))
    return JudgeCall(pick=JudgePick.INVALID, raw_tail=tail_text(reply))


def combine(first: JudgePick, second_swapped: JudgePick) -> PairOutcome:
    """The pair outcome from two calls, per the D5 table.

    ``first`` is the pick with contestant X as Draft A and Y as Draft B. ``second_swapped``
    is the second call's pick as the judge made it, with Y as Draft A and X as Draft B, so
    its ``A`` and ``B`` are swapped back here. The outcome names X as ``A`` and Y as ``B``.
    """
    if JudgePick.INVALID in (first, second_swapped):
        return PairOutcome.INVALID
    second = _unswap(second_swapped)
    if first == second:
        return PairOutcome(first.value)
    if JudgePick.TIE in (first, second):
        return PairOutcome.TIE  # a win in one order and a tie in the other
    return PairOutcome.INCONSISTENT  # the judge followed the position, not the draft


def _unswap(pick: JudgePick) -> JudgePick:
    return {JudgePick.A: JudgePick.B, JudgePick.B: JudgePick.A}.get(pick, pick)


def strip_frontmatter(text: str) -> str:
    """``text`` without a leading YAML frontmatter block; unchanged when it has none."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return text
    for position, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_DELIMITER:
            return "".join(lines[position + 1 :]).lstrip("\r\n")
    return text  # an opening delimiter with no close is not frontmatter
