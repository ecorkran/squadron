"""Shared setup for the task-gate CLI and pipeline tests (slice 933)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR

MODEL = "claude-sonnet-4-20250514"
ARCH = "project-documents/user/architecture/100-arch.md"
DESIGN = "project-documents/user/slices/194-slice.loop-step-type.md"
SINGLE = ["194-tasks.loop-step-type.md"]
SPLIT = [f"194-tasks.loop-step-type-{n}.md" for n in (1, 2)]
# P1's second line (trading-data 184:220), unchecked.
MERGE_LINE = "- [ ] Merge to `main`."
CLEAN_BODY = "# Tasks\n\n- [ ] Add the scanner\n"
OFFENDING_BODY = f"# Tasks\n\n- [ ] Add the scanner\n{MERGE_LINE}\n"
OFFENDING_LINE_NUMBER = 4

_PROJECT = ProjectInfo(
    arch_file=ARCH,
    slice_plan="100-slices.orchestration-v2",
    phase="Phase 6: Implementation",
    slice="194-slice.loop-step-type",
    name="squadron",
)


def cf_client(task_names: list[str]) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=194, name="Loop Step Type", design_file=DESIGN, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=194, files=task_names)]
    client.get_project.return_value = _PROJECT
    return client


def model_result(verdict: Verdict = Verdict.PASS) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[],
        raw_output=f"## Summary\n{verdict}\n",
        template_name="tasks",
        input_files={},
        timestamp=datetime(2026, 10, 11, 12, 0, 0),
        model=MODEL,
    )


def write_project(root: Path, bodies: dict[str, str], design_body: str = "# design\n") -> Path:
    """Write task files (name → body) and the design under ``root``."""
    for name, body in bodies.items():
        path = root / TASKS_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    design = root / DESIGN
    design.parent.mkdir(parents=True, exist_ok=True)
    design.write_text(design_body, encoding="utf-8")
    return root


def review_names(root: Path) -> set[str]:
    return {path.name for path in (root / REVIEWS_DIR).glob("*.md")}


def action_context(root: Path, client: MagicMock, template: str = "tasks") -> ActionContext:
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(MODEL, None)
    return ActionContext(
        pipeline_name=f"review-{template}-only",
        run_id="run-12345678",
        params={"template": template, "slice": 194},
        step_name=f"review-{template}",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=client,
        cwd=str(root),
    )
