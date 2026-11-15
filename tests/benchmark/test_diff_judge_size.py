"""The over-size rule (slice 426, Task 29): the longest pair prompt against the limit."""

from __future__ import annotations

from squadron.benchmark.diff_judge import check_size, normalized_diffs
from squadron.benchmark.diff_normalize import NormalizedDiff
from squadron.benchmark.diff_pairs import Pair, contestants_for, pairs_for
from squadron.benchmark.diff_prompt import diff_prompt
from tests.benchmark.diff_judge_support import CONFIG_ABSENCES, diff_text, grid, replay_input
from tests.benchmark.slice_runner_support import slice_case

CASE = slice_case()


def _setup(reference_lines: int = 1) -> tuple[list[Pair], dict[str, NormalizedDiff]]:
    big = b"".join(diff_text(f"reference{n}") for n in range(reference_lines))
    pairs = pairs_for(contestants_for(CASE, grid(CASE, {"opus": 1, "sol": 1}), big))
    return pairs, normalized_diffs(pairs)


def _longest(pairs: list[Pair], normalized: dict[str, NormalizedDiff]) -> int:
    return max(
        len(diff_prompt(CASE.task_text, normalized[p.a.ref].text, normalized[p.b.ref].text))
        for p in pairs
    )


def test_a_prompt_at_the_limit_passes_and_one_character_over_fails() -> None:
    pairs, normalized = _setup(reference_lines=3)
    longest = _longest(pairs, normalized)

    assert check_size(CASE, pairs, longest, normalized) is None
    over = check_size(CASE, pairs, longest - 1, normalized)
    assert over is not None and over.longest_chars == longest


def test_the_longest_contestant_is_named() -> None:
    pairs, normalized = _setup(reference_lines=3)

    over = check_size(CASE, pairs, 1, normalized)

    assert over is not None
    assert over.contestant.startswith("reference:")  # its diff is the longer one in its pairs


def test_one_oversized_contestant_excludes_the_whole_case() -> None:
    pairs, normalized = _setup(reference_lines=40)
    limit = _longest([p for p in pairs if not p.versus_reference], normalized) + 10

    # Every replay-vs-replay prompt fits, yet the reference's pairs do not: the case is out.
    assert check_size(CASE, [p for p in pairs if not p.versus_reference], limit, normalized) is None
    assert check_size(CASE, pairs, limit, normalized) is not None


def test_no_pair_prompt_is_shortened() -> None:
    pairs, normalized = _setup(reference_lines=5)
    longest = _longest(pairs, normalized)

    over = check_size(CASE, pairs, longest - 1, normalized)

    assert over is not None
    untruncated = max(
        len(diff_prompt(CASE.task_text, normalized[p.a.ref].text, normalized[p.b.ref].text))
        for p in pairs
    )
    assert over.longest_chars == untruncated
    for diff in normalized.values():
        assert diff.text in diff_prompt(CASE.task_text, diff.text, diff.text)


def test_forfeit_pairs_are_ignored() -> None:
    absent = replay_input(CASE, "sol", 1, outcome=CONFIG_ABSENCES[0])
    pairs = pairs_for(
        contestants_for(CASE, [replay_input(CASE, "opus", 1), absent], diff_text("reference"))
    )
    normalized = normalized_diffs(pairs)
    forfeits = [p for p in pairs if not (p.a.present and p.b.present)]
    assert forfeits  # the fixture holds forfeits

    assert check_size(CASE, forfeits, 1, normalized) is None
