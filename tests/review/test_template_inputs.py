"""Tests for the template-input registry (template_inputs.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.review.persistence import SliceInfo
from squadron.review.template_inputs import (
    TEMPLATE_INPUTS,
    TemplateInputSpec,
    missing_input_files,
    resolve_template_input_parts,
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

SLICE_INFO: SliceInfo = SliceInfo(
    index=194,
    name="loop-step-type",
    slice_name="loop-step-type-for-multi-step-bodies",
    design_file="project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md",
    task_files=["194-tasks.loop-step-type-for-multi-step-bodies.md"],
    arch_file="project-documents/user/architecture/100-arch.orchestration-v2.md",
    project="squadron",
)

CWD = "/tmp/fake-cwd"
DIFF_RANGE = "abc123...slice-194"


# ---------------------------------------------------------------------------
# Registry entries exist
# ---------------------------------------------------------------------------


def test_registry_has_all_templates() -> None:
    assert set(TEMPLATE_INPUTS.keys()) == {
        "slice",
        "tasks",
        "arch",
        "code",
        "judge.tasks-vs-slice",
        "judge.slice-vs-arch",
    }


def _resolve_one(template_name: str, info: SliceInfo = SLICE_INFO) -> dict[str, str]:
    """Resolve a template expected to yield exactly one part and return it."""
    parts = resolve_template_input_parts(template_name, info, CWD, {})
    assert len(parts) == 1
    return parts[0]


# ---------------------------------------------------------------------------
# slice template
# ---------------------------------------------------------------------------


def test_slice_template_populates_input_and_against() -> None:
    inputs = _resolve_one("slice")
    assert inputs["input"] == SLICE_INFO["design_file"]
    assert inputs["against"] == SLICE_INFO["arch_file"]


def test_slice_template_no_against_when_arch_file_empty() -> None:
    """An empty source must not set the key (not even to an empty string)."""
    info: SliceInfo = {**SLICE_INFO, "arch_file": ""}
    assert "against" not in _resolve_one("slice", info)


# ---------------------------------------------------------------------------
# tasks template
# ---------------------------------------------------------------------------


def test_tasks_template_populates_input_and_against() -> None:
    inputs = _resolve_one("tasks")
    assert inputs["input"] == (f"project-documents/user/tasks/{SLICE_INFO['task_files'][0]}")
    assert inputs["against"] == SLICE_INFO["design_file"]


def test_tasks_template_no_input_when_task_files_empty() -> None:
    """An empty fan-out source yields one part without the key."""
    info: SliceInfo = {**SLICE_INFO, "task_files": []}
    assert "input" not in _resolve_one("tasks", info)


# ---------------------------------------------------------------------------
# arch template
# ---------------------------------------------------------------------------


def test_arch_template_populates_input() -> None:
    assert _resolve_one("arch")["input"] == SLICE_INFO["arch_file"]


# ---------------------------------------------------------------------------
# code template
# ---------------------------------------------------------------------------


def test_code_template_populates_diff() -> None:
    with patch(
        "squadron.review.template_inputs.resolve_slice_diff_range",
        return_value=DIFF_RANGE,
    ) as mock_diff:
        inputs = _resolve_one("code")
        mock_diff.assert_called_once_with(SLICE_INFO["index"], CWD)
        assert inputs["diff"] == DIFF_RANGE


# ---------------------------------------------------------------------------
# Unknown template
# ---------------------------------------------------------------------------


def test_unknown_template_yields_one_unchanged_copy() -> None:
    inputs: dict[str, str] = {"existing": "value"}
    parts = resolve_template_input_parts("nonexistent", SLICE_INFO, CWD, inputs)
    assert parts == [{"existing": "value"}]
    assert parts[0] is not inputs


def test_unknown_template_does_not_raise() -> None:
    assert resolve_template_input_parts("totally-unknown", SLICE_INFO, CWD, {}) == [{}]


# ---------------------------------------------------------------------------
# judge.tasks-vs-slice template (302)
# ---------------------------------------------------------------------------


def test_judge_tasks_vs_slice_populates_input_and_against() -> None:
    inputs = _resolve_one("judge.tasks-vs-slice")
    assert inputs["input"] == (f"project-documents/user/tasks/{SLICE_INFO['task_files'][0]}")
    assert inputs["against"] == SLICE_INFO["design_file"]


def test_judge_tasks_vs_slice_no_input_when_task_files_empty() -> None:
    """An empty fan-out source yields one part without the key."""
    info: SliceInfo = {**SLICE_INFO, "task_files": []}
    assert "input" not in _resolve_one("judge.tasks-vs-slice", info)


# ---------------------------------------------------------------------------
# judge.slice-vs-arch template (302)
# ---------------------------------------------------------------------------


def test_judge_slice_vs_arch_populates_input_and_against() -> None:
    inputs = _resolve_one("judge.slice-vs-arch")
    assert inputs["input"] == SLICE_INFO["design_file"]
    assert inputs["against"] == SLICE_INFO["arch_file"]


def test_judge_slice_vs_arch_no_against_when_arch_file_empty() -> None:
    """An empty source must not set the key (not even to an empty string)."""
    info: SliceInfo = {**SLICE_INFO, "arch_file": ""}
    assert "against" not in _resolve_one("judge.slice-vs-arch", info)


# ---------------------------------------------------------------------------
# Fan-out over split task files (slice 930)
# ---------------------------------------------------------------------------

SPLIT_INFO: SliceInfo = {
    **SLICE_INFO,
    "task_files": [
        "194-tasks.loop-step-type-1.md",
        "194-tasks.loop-step-type-2.md",
        "194-tasks.loop-step-type-3.md",
    ],
}
SPLIT_PATHS = [f"project-documents/user/tasks/{name}" for name in SPLIT_INFO["task_files"]]


@pytest.mark.parametrize("template_name", ["tasks", "judge.tasks-vs-slice"])
def test_split_task_files_yield_one_part_each(template_name: str) -> None:
    parts = resolve_template_input_parts(template_name, SPLIT_INFO, CWD, {"cwd": CWD})
    assert [part["input"] for part in parts] == SPLIT_PATHS
    assert all(part["against"] == SLICE_INFO["design_file"] for part in parts)
    assert all(part["cwd"] == CWD for part in parts)


def test_caller_supplied_input_is_one_part() -> None:
    parts = resolve_template_input_parts("tasks", SPLIT_INFO, CWD, {"input": "mine.md"})
    assert len(parts) == 1
    assert parts[0]["input"] == "mine.md"
    assert parts[0]["against"] == SLICE_INFO["design_file"]


def test_two_fan_out_specs_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def _two(_info: SliceInfo, _cwd: str) -> list[str]:
        return ["a", "b"]

    monkeypatch.setitem(
        TEMPLATE_INPUTS,
        "double-fan",
        [
            TemplateInputSpec(key="input", source=_two, fans_out=True),
            TemplateInputSpec(key="against", source=_two, fans_out=True),
        ],
    )
    with pytest.raises(ValueError, match="more than one fan-out"):
        resolve_template_input_parts("double-fan", SLICE_INFO, CWD, {})


def test_inputs_are_not_mutated() -> None:
    inputs = {"cwd": CWD}
    resolve_template_input_parts("tasks", SPLIT_INFO, CWD, inputs)
    assert inputs == {"cwd": CWD}


# ---------------------------------------------------------------------------
# missing_input_files — the input/against existence guard (issue #18)
# ---------------------------------------------------------------------------


def test_missing_input_files_empty_when_keys_absent() -> None:
    assert missing_input_files({"cwd": "."}) == []


def test_missing_input_files_flags_nonexistent_input(tmp_path: Path) -> None:
    against = tmp_path / "against.md"
    against.write_text("# against\n")
    inputs = {
        "cwd": str(tmp_path),
        "input": str(tmp_path / "no-such-file.md"),
        "against": str(against),
    }
    assert missing_input_files(inputs) == [("input", str(tmp_path / "no-such-file.md"))]


def test_missing_input_files_flags_nonexistent_against(tmp_path: Path) -> None:
    input_doc = tmp_path / "input.md"
    input_doc.write_text("# input\n")
    inputs = {
        "cwd": str(tmp_path),
        "input": str(input_doc),
        "against": str(tmp_path / "gone.md"),
    }
    assert missing_input_files(inputs) == [("against", str(tmp_path / "gone.md"))]


def test_missing_input_files_accepts_cwd_relative_path(tmp_path: Path) -> None:
    """A path resolvable under inputs['cwd'] counts as present (SDK agents
    read files relative to their working directory)."""
    (tmp_path / "doc.md").write_text("# doc\n")
    inputs = {"cwd": str(tmp_path), "input": "doc.md"}
    assert missing_input_files(inputs) == []


def test_missing_input_files_flags_both(tmp_path: Path) -> None:
    inputs = {
        "cwd": str(tmp_path),
        "input": str(tmp_path / "a.md"),
        "against": str(tmp_path / "b.md"),
    }
    assert [key for key, _ in missing_input_files(inputs)] == ["input", "against"]


# ---------------------------------------------------------------------------
# Slice 917 Part 3: substituted content is delimited (#25)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("template_name", "tags"),
    [
        ("slice", ("slice_document", "architecture_document")),
        ("tasks", ("task_file", "slice_design")),
        ("arch", ("architecture_document",)),
        ("judge.slice-vs-arch", ("slice_document", "architecture_document")),
        ("judge.tasks-vs-slice", ("task_file", "slice_design")),
    ],
)
def test_substituted_content_sits_between_its_tags(template_name: str, tags: tuple[str, ...]) -> None:
    """Descriptive tags must bracket the substituted values, not merely appear.

    Without a delimiter a model cannot reliably tell the instructions from the
    material they are about, which is how a template's own example text ends
    up quoted back as output (#25).
    """
    from squadron.review.templates import get_template, load_all_templates

    load_all_templates()
    template = get_template(template_name)
    assert template is not None

    inputs = {"input": "INPUT-SENTINEL", "against": "AGAINST-SENTINEL"}
    rendered = template.build_prompt(inputs)

    sentinels = ["INPUT-SENTINEL", "AGAINST-SENTINEL"][: len(tags)]
    for tag, sentinel in zip(tags, sentinels, strict=True):
        open_tag, close_tag = f"<{tag}>", f"</{tag}>"
        assert open_tag in rendered
        assert close_tag in rendered
        assert rendered.index(open_tag) < rendered.index(sentinel) < rendered.index(close_tag)


def test_code_prompt_delimits_scope_and_output_format() -> None:
    from squadron.review.builders.code import code_review_prompt

    rendered = code_review_prompt({"cwd": "/tmp/project", "diff": "main"})

    assert rendered.index("<scope>") < rendered.index("git diff main") < rendered.index("</scope>")
    assert (
        rendered.index("<output_format>")
        < rendered.index("severity format")
        < rendered.index("</output_format>")
    )
