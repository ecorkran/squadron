"""Tests for squadron.pipeline.sources — the ``each`` source registry.

Fixtures are real ``cf list slices 900 --json`` / ``cf list tasks 900 --json``
output (captured 20260926, trimmed), parsed by the real ContextForgeClient: only
the subprocess boundary is stubbed.
"""

from __future__ import annotations

import json

import pytest

from squadron.integrations.context_forge import ContextForgeClient

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
        }

    def test_registered(self) -> None:
        from squadron.pipeline.sources import parse_source

        assert parse_source('cf.undesigned_slices("900")') == ("cf", "undesigned_slices", ["900"])
