"""Tests for squadron.pipeline.sources — the ``each`` source registry.

Fixtures are real ``cf list slices 900 --json`` / ``cf list tasks 900 --json``
output (captured 20260926, trimmed), parsed by the real ContextForgeClient: only
the subprocess boundary is stubbed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from squadron.integrations.context_forge import ContextForgeClient, SliceEntry
from squadron.pipeline.sources import (  # pyright: ignore[reportPrivateUsage]
    _design_dependencies,
    _slice_item,
)

_SLICES_DIR = "project-documents/user/slices/"

_SLICES_900 = {
    "slicePlan": "900-slices.maintenance-and-refactoring",
    "total": 7,
    "completed": 1,
    "entries": [
        {
            "index": 901,
            "name": "Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed",
            "isChecked": True,
            "designFile": f"{_SLICES_DIR}901-slice.pipeline-code-review-diff-injection.md",
            "status": "complete",
            "isActive": False,
            "isNext": False,
        },
        {
            "index": 907,
            "name": "Optional Dependency Split — `serve` and `codex` Extras",
            "isChecked": False,
            "designFile": f"{_SLICES_DIR}907-slice.optional-dependency-split-serve-and-codex-extras.md",
            "status": "deferred",
            "isActive": False,
            "isNext": False,
        },
        {
            "index": 914,
            "name": "Strict Type Checking Over the Test Suite",
            "isChecked": False,
            "designFile": f"{_SLICES_DIR}914-slice.strict-type-checking-over-the-test-suite.md",
            "status": "not_started",
            "isActive": False,
            "isNext": True,
        },
        *[
            {
                "index": index,
                "name": name,
                "isChecked": False,
                "designFile": None,
                "status": "not_started",
                "isActive": False,
                "isNext": False,
            }
            for index, name in [
                (923, "Test Suite Machine-State Isolation"),
                (924, "Recover a Review the Model Reasoned Out but Never Emitted"),
                (928, "Codex Parity for Skill Packs and Provider Access"),
                (929, "Serialize Concurrent `git worktree add` on One Checkout"),
            ]
        ],
    ],
}

_TASKS_900 = [
    {
        "index": 901,
        "name": "Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed",
        "files": ["901-tasks.pipeline-code-review-diff-injection.md"],
        "completed": 46,
        "total": 46,
        "isActive": False,
    },
    {
        "index": 907,
        "name": "Optional Dependency Split — `serve` and `codex` Extras",
        "files": ["907-tasks.optional-dependency-split-serve-and-codex-extras.md"],
        "completed": 0,
        "total": 12,
        "isActive": False,
    },
]


class StubCfClient(ContextForgeClient):
    """Real client parsing, canned subprocess output; records every call."""

    def __init__(self, slices: object = _SLICES_900, tasks: object = _TASKS_900) -> None:
        self._outputs = {"slices": slices, "tasks": tasks}
        self.calls: list[list[str]] = []

    def _run(self, args: list[str]) -> str:
        self.calls.append(args)
        return json.dumps(self._outputs[args[1]])


def _indices(items: list[dict[str, object]]) -> list[str]:
    return [str(item["index"]) for item in items]


class TestUnfinishedSlices:
    @pytest.mark.asyncio
    async def test_reads_the_requested_plan(self) -> None:
        from squadron.pipeline.sources import _cf_unfinished_slices

        client = StubCfClient()
        items = await _cf_unfinished_slices(["900"], client, {})

        assert client.calls == [["list", "slices", "900", "--json"]]
        assert _indices(items) == ["907", "914", "923", "924", "928", "929"]

    @pytest.mark.asyncio
    async def test_no_plan_reads_the_active_plan(self) -> None:
        from squadron.pipeline.sources import _cf_unfinished_slices

        client = StubCfClient()
        await _cf_unfinished_slices([], client, {})

        assert client.calls == [["list", "slices", "--json"]]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan", ["900-slices.maintenance-and-refactoring", "{plan}", "9a"])
    async def test_non_digit_plan_raises(self, plan: str) -> None:
        from squadron.pipeline.sources import _cf_unfinished_slices

        with pytest.raises(ValueError, match="plan must be an architecture index, got"):
            await _cf_unfinished_slices([plan], StubCfClient(), {})


class TestUndesignedSlices:
    @pytest.mark.asyncio
    async def test_selects_open_slices_without_a_design(self) -> None:
        from squadron.pipeline.sources import _cf_undesigned_slices

        client = StubCfClient()
        items = await _cf_undesigned_slices(["900"], client, {})

        # 907 is deferred, 914 is designed, 901 is complete.
        assert _indices(items) == ["923", "924", "928", "929"]
        assert client.calls == [["list", "slices", "900", "--json"]]

    @pytest.mark.asyncio
    async def test_item_shape(self) -> None:
        from squadron.pipeline.sources import _cf_undesigned_slices

        items = await _cf_undesigned_slices(["900"], StubCfClient(), {})

        assert items[0] == {
            "index": "923",
            "name": "Test Suite Machine-State Isolation",
            "status": "not_started",
            "design_file": "",
            "dependencies": [],
        }

    def test_registered(self) -> None:
        from squadron.pipeline.sources import parse_source

        assert parse_source('cf.undesigned_slices("900")') == ("cf", "undesigned_slices", ["900"])


# Frontmatter copied from a real slice review artifact (195's design review,
# 20260926); only ``verdict`` and the slice identity vary per test.
_REVIEW_TEMPLATE = """---
docType: review
layer: project
reviewType: slice
slice: strict-type-checking-over-the-test-suite
targetKind: slice
rulesSource: project
project: squadron
verdict: {verdict}
verdictSource: stated
sourceDocument: project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: efe8eb010180b4bcb618e63bc2254d1d0ec97e81
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Boundary tension with the parent architecture"
---

# Review: slice — slice 914
"""

_REVIEW_914 = "914-review.slice.strict-type-checking-over-the-test-suite.md"


class TestSlicesNeedingTasks:
    @pytest.fixture(autouse=True)
    def _in_tmp_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        # Review paths are relative to the process cwd, as the save path's are.
        monkeypatch.chdir(tmp_path)
        reviews = tmp_path / "project-documents" / "user" / "reviews"
        reviews.mkdir(parents=True)
        return reviews

    def _write_review(self, text: str) -> None:
        (Path("project-documents/user/reviews") / _REVIEW_914).write_text(text, encoding="utf-8")

    async def _run(self, accept: str = "review.concerns_or_better") -> list[dict[str, object]]:
        from squadron.pipeline.sources import _cf_slices_needing_tasks

        return await _cf_slices_needing_tasks(["900", accept], StubCfClient(), {})

    @pytest.mark.asyncio
    async def test_900_plan_selects_only_914_flagged_missing_review(self) -> None:
        items = await self._run()

        assert _indices(items) == ["914"]
        assert items[0]["flag_reason"] == "no design review found"

    @pytest.mark.asyncio
    async def test_passing_review_is_not_flagged(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))

        items = await self._run()

        assert _indices(items) == ["914"]
        assert "flag_reason" not in items[0]

    @pytest.mark.asyncio
    async def test_concerns_meets_concerns_or_better(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="CONCERNS"))

        assert "flag_reason" not in (await self._run())[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("verdict", "accept", "reason"),
        [
            ("FAIL", "review.concerns_or_better", "(FAIL < CONCERNS)"),
            ("CONCERNS", "review.pass", "(CONCERNS < PASS)"),
        ],
    )
    async def test_below_threshold_is_flagged(self, verdict: str, accept: str, reason: str) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict=verdict))

        items = await self._run(accept)

        assert items[0]["flag_reason"] == f"design review below threshold {reason}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text",
        [
            _REVIEW_TEMPLATE.format(verdict="MAYBE"),
            _REVIEW_TEMPLATE.replace("verdict: {verdict}\n", ""),
            "no frontmatter at all\n",
            "---\nverdict: [unclosed\n---\n",
        ],
    )
    async def test_unreadable_verdict_is_flagged(self, text: str) -> None:
        self._write_review(text)

        items = await self._run()

        assert items[0]["flag_reason"] == "design review verdict unreadable"

    # --- slice 196 D11: a tasked slice with an unsettled tasks review is selected too ---

    _TASKED = [*_TASKS_900, {"index": 914, "files": ["914-tasks.strict.md"]}]

    def _write_tasks_review(self, text: str) -> None:
        name = _REVIEW_914.replace("review.slice.", "review.tasks.")
        (Path("project-documents/user/reviews") / name).write_text(text, encoding="utf-8")

    async def _run_tasked(self, accept: str = "review.pass") -> list[dict[str, object]]:
        from squadron.pipeline.sources import _cf_slices_needing_tasks

        client = StubCfClient(tasks=self._TASKED)
        return await _cf_slices_needing_tasks(["900", accept], client, {})

    @pytest.mark.asyncio
    async def test_tasked_slice_with_no_tasks_review_is_selected(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))

        items = await self._run_tasked()

        assert _indices(items) == ["914"]
        assert "flag_reason" not in items[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text",
        [
            _REVIEW_TEMPLATE.format(verdict="MAYBE"),
            "no frontmatter at all\n",
        ],
    )
    async def test_tasked_slice_with_an_unreadable_tasks_review_is_selected(self, text: str) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))
        self._write_tasks_review(text)

        assert _indices(await self._run_tasked()) == ["914"]

    @pytest.mark.asyncio
    async def test_tasked_slice_with_a_tasks_review_below_threshold_is_selected(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))
        self._write_tasks_review(_REVIEW_TEMPLATE.format(verdict="CONCERNS"))

        assert _indices(await self._run_tasked("review.pass")) == ["914"]

    @pytest.mark.asyncio
    async def test_tasked_slice_with_a_passing_tasks_review_is_not_selected(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))
        self._write_tasks_review(_REVIEW_TEMPLATE.format(verdict="PASS"))

        assert await self._run_tasked() == []

    @pytest.mark.asyncio
    async def test_concerns_tasks_review_settles_under_concerns_or_better(self) -> None:
        self._write_review(_REVIEW_TEMPLATE.format(verdict="PASS"))
        self._write_tasks_review(_REVIEW_TEMPLATE.format(verdict="CONCERNS"))

        assert await self._run_tasked("review.concerns_or_better") == []

    @pytest.mark.asyncio
    async def test_design_review_flag_applies_first_to_a_tasked_slice(self) -> None:
        """No design review: the slice is selected (no tasks review) but flagged for the design."""
        items = await self._run_tasked()

        assert _indices(items) == ["914"]
        assert items[0]["flag_reason"] == "no design review found"

    def test_tasks_review_reasons_name_the_review(self) -> None:
        from squadron.pipeline.loop_config import LoopCondition
        from squadron.pipeline.sources import _review_flag  # pyright: ignore[reportPrivateUsage]

        entry = SliceEntry(
            index=914,
            name="Strict Type Checking Over The Test Suite",
            design_file=f"{_SLICES_DIR}914-slice.strict-type-checking-over-the-test-suite.md",
            status="not_started",
        )
        self._write_tasks_review(_REVIEW_TEMPLATE.format(verdict="CONCERNS"))

        assert _review_flag(entry, "tasks", LoopCondition.REVIEW_PASS) == (
            "tasks review below threshold (CONCERNS < PASS)"
        )

    @pytest.mark.asyncio
    async def test_reads_the_requested_plan(self) -> None:
        from squadron.pipeline.sources import _cf_slices_needing_tasks

        client = StubCfClient()
        await _cf_slices_needing_tasks(["900", "review.pass"], client, {})

        assert ["list", "tasks", "900", "--json"] in client.calls
        assert ["list", "slices", "900", "--json"] in client.calls

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("args", "match"),
        [
            (["900", "action.success"], "not a review verdict threshold"),
            (["900", "PASS"], "Invalid accept threshold"),
            (["900"], "requires"),
        ],
    )
    async def test_bad_accept_raises(self, args: list[str], match: str) -> None:
        from squadron.pipeline.sources import _cf_slices_needing_tasks

        with pytest.raises(ValueError, match=match):
            await _cf_slices_needing_tasks(args, StubCfClient(), {})


class TestSliceDependencies:
    """Slice 196 D9: dependencies come from the design's frontmatter, leniently parsed."""

    def _entry(self, design_file: str | None, index: int = 196) -> SliceEntry:
        return SliceEntry(index=index, name="Slice", design_file=design_file, status="not_started")

    def _design(self, tmp_path: Path, frontmatter_line: str | None) -> str:
        lines = ["---", "docType: slice-design"]
        if frontmatter_line is not None:
            lines.append(frontmatter_line)
        design = tmp_path / "196-slice.example.md"
        design.write_text("\n".join([*lines, "---", "", "body", ""]), encoding="utf-8")
        return str(design)

    def test_integer_elements(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, "dependencies: [195, 181]")
        assert _design_dependencies(self._entry(design)) == [195, 181]

    def test_string_and_prefixed_string_elements(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, 'dependencies: ["195", "181-slice.pool-resolver", 149]')
        assert _design_dependencies(self._entry(design)) == [195, 181, 149]

    def test_element_without_a_leading_integer_is_dropped_with_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        design = self._design(tmp_path, "dependencies: [195, foundation]")

        with caplog.at_level(logging.WARNING, logger="squadron.pipeline.sources"):
            result = _design_dependencies(self._entry(design))

        assert result == [195]
        assert any("slice 196" in r.message and "foundation" in r.message for r in caplog.records)

    def test_an_undecodable_design_warns_and_reads_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        design = tmp_path / "196-slice.example.md"
        design.write_bytes(b"---\ndependencies: [195]\n---\n\xff\xfe\n")

        with caplog.at_level(logging.WARNING, logger="squadron.pipeline.sources"):
            result = _design_dependencies(self._entry(str(design)))

        assert result == []
        assert "cannot read design" in caplog.text

    def test_no_design_file_means_no_dependencies(self) -> None:
        assert _design_dependencies(self._entry(None)) == []
        assert _design_dependencies(self._entry("")) == []

    def test_no_dependencies_key(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, None)
        assert _design_dependencies(self._entry(design)) == []

    def test_empty_list(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, "dependencies: []")
        assert _design_dependencies(self._entry(design)) == []

    def test_a_scalar_value_is_read_as_one_element(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, "dependencies: 195")
        assert _design_dependencies(self._entry(design)) == [195]

    def test_missing_design_file_warns_and_reads_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="squadron.pipeline.sources"):
            result = _design_dependencies(self._entry(str(tmp_path / "gone.md")))

        assert result == []
        assert any("not found" in r.message for r in caplog.records)

    def test_the_real_195_design_parses(self) -> None:
        """The format the parser meets in production, not a hand-built fixture."""
        design = next(Path("project-documents/user/slices").glob("195-slice.*.md"))
        assert _design_dependencies(self._entry(str(design), index=195)) == [194, 181, 909, 927]

    def test_slice_item_carries_the_dependencies(self, tmp_path: Path) -> None:
        design = self._design(tmp_path, "dependencies: [195]")
        assert _slice_item(self._entry(design))["dependencies"] == [195]
