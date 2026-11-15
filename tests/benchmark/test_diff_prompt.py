"""The diff judge's prompt (slice 426, Task 28)."""

from __future__ import annotations

from squadron.benchmark.diff_prompt import (
    diff_judge_prompt,
    diff_judge_prompt_hash,
    diff_prompt,
)
from squadron.data import data_dir
from squadron.metrology.replay_models import JudgePick
from squadron.replay.judge import judge_prompt_hash, parse_verdict

TASK = "## File: design.md\n---\nslice: demo\n---\nBuild the thing.\n"
DIFF_ONE = "diff --git a/one.py b/one.py\n+one\n"
DIFF_TWO = "diff --git a/two.py b/two.py\n+two\n"


def test_sections_appear_in_order_with_the_task_and_both_diffs_verbatim() -> None:
    prompt = diff_prompt(TASK, DIFF_ONE, DIFF_TWO)

    positions = [prompt.index(h) for h in ("## Task", "## Implementation A", "## Implementation B")]
    assert positions == sorted(positions)
    assert TASK in prompt and DIFF_ONE in prompt and DIFF_TWO in prompt
    assert prompt.index(DIFF_ONE) < prompt.index("## Implementation B") < prompt.index(DIFF_TWO)
    assert prompt.index(TASK) < prompt.index("## Implementation A")


def test_swapping_a_and_b_swaps_the_sections() -> None:
    forward = diff_prompt(TASK, DIFF_ONE, DIFF_TWO)
    swapped = diff_prompt(TASK, DIFF_TWO, DIFF_ONE)

    assert forward != swapped
    assert swapped.index(DIFF_TWO) < swapped.index("## Implementation B") < swapped.index(DIFF_ONE)


def test_the_frontmatter_is_not_part_of_what_the_judge_reads() -> None:
    assert diff_judge_prompt().startswith("---\n")
    assert not diff_prompt(TASK, DIFF_ONE, DIFF_TWO).startswith("---")
    assert "docType" not in diff_prompt(TASK, DIFF_ONE, DIFF_TWO)


def test_the_prompt_ends_with_the_winner_instruction_parse_verdict_reads() -> None:
    assert "WINNER: X" in diff_judge_prompt()
    assert parse_verdict("Implementation A covers more of the tasks.\nWINNER: A").pick is JudgePick.A
    assert parse_verdict("neither is better\nWINNER: TIE").pick is JudgePick.TIE


def test_the_hash_is_the_files_and_differs_from_the_design_judges() -> None:
    assert len(diff_judge_prompt_hash()) == 64
    assert diff_judge_prompt_hash() != judge_prompt_hash()


def test_the_packaged_file_is_found_through_data_dir() -> None:
    assert data_dir().joinpath("benchmark", "pairwise-diff-judge.md").is_file()
