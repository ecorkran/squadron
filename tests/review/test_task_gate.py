"""Tests for the deterministic task-file merge-step gate (slice 933)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.core.usage import TokenUsage
from squadron.metrology.identity import read_review_frontmatter
from squadron.review.models import Severity, Verdict, VerdictSource
from squadron.review.persistence import SliceInfo, save_review_result
from squadron.review.task_gate import (
    MERGE_OBJECT_WINDOW,
    TASK_GATE_MODEL,
    MergeStepLine,
    merge_gate_results,
    scan_merge_steps,
)
from squadron.review.templates import BuiltinReviewTemplate

FIXTURES = Path(__file__).parent / "fixtures" / "task_gate"

# Expected hit lines within each excerpt; fixtures/task_gate/README.md maps them
# back to the source files' line numbers.
POSITIVE_EXCERPTS: dict[str, list[int]] = {
    "p1.md": [4, 13],
    "p2.md": [7, 12],
    "p3.md": [4, 5],
    "p4.md": [7, 8],
    "p5.md": [7],
    "p6.md": [7],
}

# The design's "Not flagged" list, verbatim.
DESIGN_NEGATIVES = [
    "- [ ] Merge defaults from config into profile",
    "- [ ] Merge slice config overrides",
    "- [ ] Fix merge blocker",
    "- [ ] Zero errors is the merge gate",
    "- [ ] Call mergeFixResults",
    "- [ ] Merges built-in and user profiles",
    "- [ ] Compute merge-base",
    "- [ ] Run git log --no-merges",
    "- [ ] Run git merge-base main HEAD",
]

P1_SECOND_LINE = "  - [x] Merge to `main`."


@pytest.mark.parametrize(("name", "expected"), POSITIVE_EXCERPTS.items())
def test_real_excerpts_flag_expected_lines(name: str, expected: list[int]) -> None:
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    hits = scan_merge_steps("\n".join(lines))
    assert [hit.line_number for hit in hits] == expected
    for hit in hits:
        assert hit.text == lines[hit.line_number - 1].strip()


def test_squadron_negatives_excerpt_is_clean() -> None:
    text = (FIXTURES / "squadron_negatives.md").read_text(encoding="utf-8")
    assert scan_merge_steps(text) == []


@pytest.mark.parametrize("line", DESIGN_NEGATIVES)
def test_design_negatives_not_flagged(line: str) -> None:
    assert scan_merge_steps(line) == []


def test_frontmatter_and_prose_not_flagged() -> None:
    text = (
        "---\n"
        "docType: tasks\n"
        "projectState: slice branch merged to main\n"
        "---\n"
        "\n"
        "Slice 183 complete and merged to main\n"
    )
    assert scan_merge_steps(text) == []


def test_heading_flagged() -> None:
    hits = scan_merge_steps("intro\n\n## Merge to `main`.\n")
    assert [hit.line_number for hit in hits] == [3]


@pytest.mark.parametrize("line", ["- [ ] Merge", "    - [x] merge to `main`."])
def test_bare_word_and_indented_lowercase_flagged(line: str) -> None:
    assert len(scan_merge_steps(line)) == 1


def test_p1_second_line_flagged_unchecked() -> None:
    assert len(scan_merge_steps(P1_SECOND_LINE.replace("[x]", "[ ]"))) == 1


@pytest.mark.parametrize(
    "line",
    [
        "- [ ] Commit and merge",
        "- [ ] Commit, then merge",
        "- [ ] Merge and release",
        "- [ ] Merge, tag, and publish",
    ],
)
def test_joined_release_verb_flagged(line: str) -> None:
    assert len(scan_merge_steps(line)) == 1


def _window_line(filler_count: int) -> str:
    fillers = " ".join(f"word{index}" for index in range(filler_count))
    return f"- [ ] Merge {fillers} branch"


def test_object_at_window_edge_flagged() -> None:
    assert len(scan_merge_steps(_window_line(MERGE_OBJECT_WINDOW - 1))) == 1


@pytest.mark.parametrize(
    ("line", "rule"),
    [
        ("- [ ] Merge to `main`.", "leading_merge_word"),
        ("- [ ] Commit and merge", "joined_release_verb"),
        ("- [ ] Then the slice branch gets merged into main", "git_object_window"),
        ("- [ ] Success: branch merged, tree clean", "merged_success_criterion"),
    ],
)
def test_hit_names_the_matching_rule(line: str, rule: str) -> None:
    [hit] = scan_merge_steps(line)
    assert hit.rule == rule


def test_object_past_window_not_flagged() -> None:
    assert scan_merge_steps(_window_line(MERGE_OBJECT_WINDOW)) == []


def _inputs(path: str) -> dict[str, str]:
    return {"input": path, "against": "design.md", "cwd": "."}


HIT = MergeStepLine(line_number=12, text="- [ ] Merge to `main`.", rule="leading_merge_word")


def test_no_hits_gives_no_results() -> None:
    assert merge_gate_results([(_inputs("a.md"), []), (_inputs("b.md"), [])]) == {}


def test_only_offending_part_gets_a_result() -> None:
    clean, offending = _inputs("part-1.md"), _inputs("part-2.md")
    results = merge_gate_results([(clean, []), (offending, [HIT])])
    assert list(results) == ["part-2.md"]
    assert results["part-2.md"].input_files == offending


def test_fail_result_fields() -> None:
    result = merge_gate_results([(_inputs("t.md"), [HIT])])["t.md"]
    assert result.verdict is Verdict.FAIL
    assert result.template_name == BuiltinReviewTemplate.TASKS
    assert result.model == TASK_GATE_MODEL
    assert result.verdict_source is VerdictSource.IMPOSED
    assert result.tools_given is None
    assert result.tool_calls_made is None
    assert result.profile is None
    assert result.turns is None
    assert result.duration_seconds is None
    assert result.usage == TokenUsage()
    assert "No model ran" in result.raw_output
    [finding] = result.findings
    assert finding.severity is Severity.FAIL
    assert "12" in finding.title
    assert HIT.text in finding.description
    assert HIT.rule in finding.description


def test_saved_artifact_reads_back(tmp_path: Path) -> None:
    result = merge_gate_results([(_inputs("t.md"), [HIT])])["t.md"]
    slice_info = SliceInfo(
        index=933,
        name="gate",
        slice_name="gate",
        design_file=None,
        task_files=[],
        arch_file="",
        project="squadron",
    )
    saved = save_review_result(result, "tasks", slice_info=slice_info, reviews_dir=tmp_path)

    frontmatter = read_review_frontmatter(saved)
    assert frontmatter["aiModel"] == TASK_GATE_MODEL
    assert frontmatter["verdictSource"] == "imposed"
    assert frontmatter["verdict"] == "FAIL"
    assert "toolsGiven" not in frontmatter
    assert "toolCallsMade" not in frontmatter
