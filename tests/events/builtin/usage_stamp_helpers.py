"""Shared builders for the usage-stamp tests: a temp project, a fake cf client, a context."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.events import EventType
from squadron.events.contexts import PostActionContext
from squadron.pipeline.models import ActionResult
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.providers.base import USAGE_KEY
from squadron.review.persistence import ARCHITECTURE_DIR, SLICES_DIR, TASKS_DIR

# Frontmatter copied from this repo's real slice design, task file and architecture doc.
SLICE_FRONT = """---
docType: slice-design
slice: artifact-usage-stamping
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [175, 176]
interfaces: [179]
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---
"""
TASKS_FRONT = """---
docType: tasks
slice: artifact-usage-stamping
project: squadron
lld: user/slices/178-slice.artifact-usage-stamping.md
dependencies: [175, 176]
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---
"""
ARCH_FRONT = """---
docType: architecture
layer: project
project: squadron
archIndex: 140
component: pipeline-foundation
dateCreated: 20260221
dateUpdated: 20261016
status: complete
---
"""
BODY = "\n# Body\n\nText with `---` inside and trailing spaces.  \n"

DESIGN_REL = SLICES_DIR / "178-slice.example.md"
TASKS_REL = TASKS_DIR / "178-tasks.example.md"
ARCH_REL = Path(ARCHITECTURE_DIR) / "140-arch.pipeline-foundation.md"


def write_doc(root: Path, rel: Path, front: str, body: str = BODY) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(front + body, encoding="utf-8")
    return path


def fake_cf_client(task_files: list[str] | None = None) -> MagicMock:
    cf_client = MagicMock()
    cf_client.list_slices.return_value = [
        SimpleNamespace(index=178, name="Example", design_file=str(DESIGN_REL))
    ]
    files = ["178-tasks.example.md"] if task_files is None else task_files
    cf_client.list_tasks.return_value = [SimpleNamespace(index=178, files=files)]
    cf_client.get_project.return_value = SimpleNamespace(arch_file=str(ARCH_REL), name="squadron")
    return cf_client


def usage_record(cost_usd: float | None = 0.5, turns: int | None = 2) -> UsageRecord:
    return UsageRecord(
        model="m",
        alias=None,
        profile=None,
        effort=None,
        turns=turns,
        duration_seconds=4.0,
        usage=TokenUsage(prompt=100, completion=10),
        cost_usd=cost_usd,
        cost_basis=CostBasis.PROVIDER if cost_usd is not None else None,
    )


def post_action_context(
    cwd: Path,
    *,
    kind: ArtifactKind | None = ArtifactKind.DESIGN,
    params: dict[str, object] | None = None,
    record: UsageRecord | None = None,
    metadata: dict[str, object] | None = None,
    action_type: str = "dispatch",
    success: bool = True,
    iteration: int = 0,
    cf_client: MagicMock | None = None,
) -> PostActionContext:
    if metadata is None:
        metadata = {USAGE_KEY: (record or usage_record()).to_dict()}
    return PostActionContext(
        event=EventType.POST_ACTION,
        cwd=str(cwd),
        params={"slice": "178"} if params is None else params,
        action_type=action_type,
        result=ActionResult(success=success, action_type=action_type, outputs={}, metadata=metadata),
        run_id="run-1",
        run_started_at=datetime.now(tz=UTC),
        run_state_error=None,
        step_name="design",
        step_type="design",
        expected_artifact_kind=kind,
        iteration=iteration,
        cf_client=cf_client or fake_cf_client(),
    )
