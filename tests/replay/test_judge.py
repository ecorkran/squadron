"""The pairwise judge's verdict parser, order-swap rule and frontmatter strip (slice 177 D5).

The inline replies are constructed to exercise each documented form. The files in
``fixtures/judge_replies/`` are replies captured from a real judge (opus, via the production
dispatcher) during slice verification: ``plain`` as the prompt produces it, and the other
four provoked by adding a format instruction to a short two-draft comparison.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from squadron.data import data_dir
from squadron.metrology.replay_models import JudgePick, PairOutcome
from squadron.replay.judge import (
    combine,
    judge_prompt,
    judge_prompt_hash,
    parse_verdict,
    strip_frontmatter,
)

A, B, TIE, INVALID = JudgePick.A, JudgePick.B, JudgePick.TIE, JudgePick.INVALID


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Draft A is tighter.\nWINNER: A", A),
        ("Draft B covers the edge case.\n**WINNER: B**", B),
        ("Both fine.\nwinner: tie", TIE),
        ("Reasoning.\nWINNER: A   \n", A),
        ("Reasoning.\nwinner = tie", TIE),
        ("**WINNER:** B", B),
        ("WINNER: `A`.", A),
        ("> ## WINNER: B", B),
        ("WINNER: A\nOn reflection that was wrong.\nWINNER: B", B),
        ("Reasoning.\r\nWINNER: TIE\r\n", TIE),
    ],
)
def test_parse_verdict_forms(reply: str, expected: JudgePick) -> None:
    assert parse_verdict(reply).pick is expected


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I think Draft A is better, but both have merit.",
        "The winner: Alpha is clearly better.",  # a sentence, not a verdict line
        "WINNER: C",
        "WINNER:",
    ],
)
def test_no_verdict_is_invalid_with_the_raw_tail(reply: str) -> None:
    call = parse_verdict(reply)

    assert call.pick is INVALID
    assert call.raw_tail == (reply.strip() or "(empty response)")


def test_the_raw_tail_of_a_long_reply_is_bounded_and_keeps_the_end() -> None:
    reply = "x" * 5000 + " the very end"

    call = parse_verdict(reply)

    assert call.raw_tail.endswith("the very end") and len(call.raw_tail) < 1000


@pytest.mark.parametrize(
    ("first", "second_swapped", "expected"),
    [
        # X is Draft A in the first call and Draft B in the second, so the second call's
        # labels are swapped: the judge saying "B" there means X again.
        (A, B, PairOutcome.A),  # X wins both
        (B, A, PairOutcome.B),  # Y wins both
        (TIE, TIE, PairOutcome.TIE),
        (A, TIE, PairOutcome.TIE),  # a win in one order and a tie in the other
        (TIE, A, PairOutcome.TIE),
        (B, TIE, PairOutcome.TIE),
        (TIE, B, PairOutcome.TIE),
        (A, A, PairOutcome.INCONSISTENT),  # the judge followed the position, not the draft
        (B, B, PairOutcome.INCONSISTENT),
        (INVALID, A, PairOutcome.INVALID),
        (B, INVALID, PairOutcome.INVALID),
        (INVALID, INVALID, PairOutcome.INVALID),
    ],
)
def test_combine_covers_every_row_of_the_order_swap_table(
    first: JudgePick, second_swapped: JudgePick, expected: PairOutcome
) -> None:
    assert combine(first, second_swapped) is expected


def test_strip_frontmatter_removes_a_leading_block() -> None:
    text = "---\ndocType: slice\nstatus: draft\n---\n\n# Title\n\nBody\n"

    assert strip_frontmatter(text) == "# Title\n\nBody\n"


def test_strip_frontmatter_handles_crlf() -> None:
    assert strip_frontmatter("---\r\na: 1\r\n---\r\n# T\r\n") == "# T\r\n"


@pytest.mark.parametrize(
    "text",
    ["# Title\n\nBody\n", "", "---\nno closing delimiter\n# Title\n", "text\n---\na: 1\n---\n"],
)
def test_text_without_leading_frontmatter_is_unchanged(text: str) -> None:
    assert strip_frontmatter(text) == text


def test_the_prompt_hash_is_the_sha256_of_the_packaged_file() -> None:
    path = data_dir() / "replay" / "pairwise-judge.md"

    assert judge_prompt_hash() == hashlib.sha256(path.read_bytes()).hexdigest()
    assert "WINNER" in judge_prompt()


_REAL_REPLIES = Path(__file__).parent / "fixtures" / "judge_replies"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("plain", A),
        ("bold", A),
        ("lowercase", A),
        ("trailing_whitespace", A),
        ("no_verdict", INVALID),
    ],
)
def test_real_judge_replies_parse(name: str, expected: JudgePick) -> None:
    reply = (_REAL_REPLIES / f"{name}.txt").read_text(encoding="utf-8")

    call = parse_verdict(reply)

    assert call.pick is expected
    assert call.raw_tail  # the tail is kept for every reply, valid or not


def test_the_real_reply_fixtures_still_show_the_variant_they_stand_for() -> None:
    """A fixture that drifted to a plain reply would stop testing its variant."""
    read = {p.stem: p.read_text(encoding="utf-8") for p in _REAL_REPLIES.glob("*.txt")}

    assert read["plain"].rstrip().endswith("WINNER: A")
    assert "**WINNER: A**" in read["bold"]
    assert read["lowercase"].rstrip().endswith("winner: a")
    assert read["trailing_whitespace"].endswith("WINNER: A   ")
    assert "winner" not in read["no_verdict"].lower().replace("the winner", "")
