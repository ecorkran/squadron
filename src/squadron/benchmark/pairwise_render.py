"""The pairwise section's text lines (slice 426 D17)."""

from __future__ import annotations

from squadron.benchmark.pair_row import PairRow, verdict_text
from squadron.benchmark.pairwise_models import PairwiseConfigRow, PairwiseSection
from squadron.benchmark.report_rows import NO_VALUE
from squadron.metrology.grade_models import PairVerdict

PROMPT_HASH_CHARS = 8
REFERENCE_NOTE = "(reference line, not ranked)"


def _strength(row: PairwiseConfigRow) -> str:
    if row.strength is None:
        return f"no finite strength: {row.reason}"
    return f"{row.strength:.2f}"


def _pair_line(pair: PairRow) -> str:
    head = f"  {pair.label_a} vs {pair.label_b}"
    if pair.verdict is PairVerdict.TOO_FEW_CASES:
        return f"{head}   d {pair.mean_difference:+.2f}  too few cases ({pair.n_cases})"
    return (
        f"{head}   d {pair.mean_difference:+.2f}  [{pair.low:+.2f}, {pair.high:+.2f}]  "
        f"{verdict_text(pair)}   (n={pair.n_cases} cases)"
    )


def pairwise_lines(section: PairwiseSection) -> list[str]:
    """The section after the review findings: a table, the reference line, the pairs, the counts."""
    head = f"pairwise (judge {section.judge_alias}, prompt {section.prompt_hash[:PROMPT_HASH_CHARS]})"
    width = max([len(head)] + [len(row.label) + 2 for row in section.configs])
    lines = [
        "",
        f"{head:<{width}}  strength   W   L   T  inc  inv  forfeit  pairs",
    ]
    for row in section.configs:
        numbers = (
            f"{row.wins:>3} {row.losses:>3} {row.ties:>3} {row.inconsistent:>4} "
            f"{row.invalid:>4} {row.forfeits:>8} {row.pairs:>6}"
        )
        lines.append(f"  {row.label:<{width - 2}}  {_strength(row):>8}  {numbers}")
    if section.reference is not None:
        ref = section.reference
        value = (
            f"{ref.strength:.2f}" if ref.strength is not None else f"no finite strength: {ref.reason}"
        )
        lines.append(f"  {'reference':<{width - 2}}  {value:>8}  {REFERENCE_NOTE}")
    lines += [_pair_line(pair) for pair in section.pairs] or [f"  {NO_VALUE} (fewer than two configs)"]
    counts = section.counts
    limit = "" if counts.over_size_limit is None else f" (limit {counts.over_size_limit} chars)"
    lines.append(
        f"judged {counts.judged} · over size {counts.over_size}{limit} · "
        f"harness-absent {counts.harness_absent} · pending {counts.pending}"
    )
    if section.others:
        listed = ", ".join(
            f"{o.alias} (prompt {o.prompt_hash[:PROMPT_HASH_CHARS]}) {o.judgments}"
            for o in section.others
        )
        lines.append(f"other judges: {listed}")
    return lines
