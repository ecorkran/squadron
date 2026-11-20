"""Lenient comb decisions parser (slice 430, Patterns: decisions parser)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadron.metrology.recall_run_models import CombVerdict
from squadron.recipes.decisions import parse_decisions

FIXTURES = Path(__file__).parent / "fixtures" / "decisions"
KEEP, DROP, UNDECIDED = CombVerdict.KEEP, CombVerdict.DROP, CombVerdict.UNDECIDED


@pytest.mark.parametrize(
    ("line", "verdict", "reason"),
    [
        ("F3: KEEP — reason here", KEEP, "reason here"),
        ("F3 - KEEP: reason here", KEEP, "reason here"),
        ("**F3**: keep", KEEP, None),
        ("F3: DROP - hyphen reason", DROP, "hyphen reason"),
        ("F3: drop – en dash reason", DROP, "en dash reason"),
        ("F3 — Drop — em dash", DROP, "em dash"),
        ("- **F3**: `KEEP` — in a list", KEEP, "in a list"),
        ("### [FAIL] F3: KEEP. The payload is read wrong", KEEP, "The payload is read wrong"),
        ("### [NOTE] F3: Module-level assert — DROP", DROP, "Module-level assert"),
        ("f3: keep — lower-case id", KEEP, "lower-case id"),
    ],
)
def test_format_variants(line: str, verdict: CombVerdict, reason: str | None) -> None:
    parsed = parse_decisions(f"Some preamble.\n{line}\n", ["F3"])
    decision = parsed.decisions["F3"]
    assert (decision.verdict, decision.reason) == (verdict, reason)


@pytest.mark.parametrize(
    "line",
    [
        "Checked F1 and F2 against the code; both hold up.",
        "Verdict: no findings to keep. The review has one finding, F1, and it is DROP.",
        "**F1**: Confirmed as stated — the fakes return object.",
        "**Verdict:** Fix one finding (F1) before merging.",
    ],
)
def test_prose_mentioning_ids_is_not_a_decision(line: str) -> None:
    assert parse_decisions(line, ["F1"]).is_empty


def test_first_verdict_wins_and_repeats_are_counted() -> None:
    raw = "F1: KEEP — first\nF2: DROP — x\nF1: DROP — second\n### [FAIL] F1: DROP. third\n"
    parsed = parse_decisions(raw, ["F1", "F2"])
    assert parsed.decisions["F1"].verdict is KEEP
    assert parsed.duplicate_decisions == 2


def test_unknown_ids_are_counted_and_not_recorded() -> None:
    parsed = parse_decisions("F1: KEEP — a\nF9: DROP — b\nP2: KEEP — c\n", ["F1"])
    assert set(parsed.decisions) == {"F1"}
    assert parsed.unknown_ids == 2


def test_missing_ids_are_undecided_not_dropped() -> None:
    parsed = parse_decisions("F1: KEEP — a\n", ["F1", "F2"])
    assert parsed.decisions["F2"].verdict is UNDECIDED
    assert parsed.duplicate_decisions == 0


@pytest.mark.parametrize("raw", ["", "I could not read the code.\nNo decisions."])
def test_no_decision_line_gives_empty_parse(raw: str) -> None:
    parsed = parse_decisions(raw, ["F1", "F2"])
    assert parsed.is_empty
    assert (parsed.duplicate_decisions, parsed.unknown_ids) == (0, 0)


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("*.json")), ids=lambda path: path.stem)
def test_real_comb_outputs_parse_fully(fixture: Path) -> None:
    doc = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = parse_decisions(doc["raw_output"], doc["finding_ids"])
    verdicts = {finding_id: decision.verdict.value for finding_id, decision in parsed.decisions.items()}
    assert verdicts == doc["expected"]
    assert UNDECIDED.value not in verdicts.values()


def test_fixtures_cover_each_provider() -> None:
    providers = {path.stem.split("-")[0] for path in FIXTURES.glob("*.json")}
    assert {"claude", "codex", "openrouter"} <= providers
