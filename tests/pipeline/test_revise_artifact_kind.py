"""A loop's revise dispatch declares the artifact it rewrites (slice 178 walkthrough fix).

The built-in pipelines revise with a plain ``dispatch`` step, not a phase step, so
without ``artifact:`` the post-action stamps (revision, usage) never saw a kind.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import squadron
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.dispatch import ARTIFACT_KEY, DispatchStepType, step_artifact_kind
from squadron.pipeline.steps.phase import ArtifactKind, PhaseStepType
from tests.pipeline.test_executor import _dispatch_writer, make_pipeline, phase_action_registry

BUILTIN_PIPELINES = Path(squadron.__file__).parent / "data" / "pipelines"


def _dispatch(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="dispatch", name="revise", config=config)


def test_dispatch_artifact_validates_kind() -> None:
    assert DispatchStepType().validate(_dispatch({ARTIFACT_KEY: "design"})) == []
    errors = DispatchStepType().validate(_dispatch({ARTIFACT_KEY: "code"}))
    assert [e.field for e in errors] == [ARTIFACT_KEY]


def test_dispatch_artifact_not_passed_to_action() -> None:
    assert DispatchStepType().expand(_dispatch({ARTIFACT_KEY: "tasks"})) == [("dispatch", {})]


@pytest.mark.parametrize(
    ("impl", "config", "expected"),
    [
        (PhaseStepType("design"), {}, ArtifactKind.DESIGN),
        (DispatchStepType(), {ARTIFACT_KEY: "tasks"}, ArtifactKind.TASKS),
        (DispatchStepType(), {}, None),
        (PhaseStepType("implement"), {}, None),
    ],
)
def test_step_artifact_kind(
    impl: object, config: dict[str, object], expected: ArtifactKind | None
) -> None:
    assert step_artifact_kind(impl, _dispatch(config)) == expected


@pytest.mark.parametrize(
    ("pipeline", "loop_kinds"),
    [
        ("P4", [ArtifactKind.DESIGN]),
        ("P5", [ArtifactKind.TASKS]),
        ("P45", [ArtifactKind.DESIGN, ArtifactKind.TASKS]),
        ("P456", [ArtifactKind.DESIGN, ArtifactKind.TASKS, None]),
        ("P56", [ArtifactKind.TASKS, None]),
    ],
)
def test_builtin_revise_steps_declare_their_artifact(
    pipeline: str, loop_kinds: list[ArtifactKind | None]
) -> None:
    definition = load_pipeline(str(BUILTIN_PIPELINES / f"{pipeline}.yaml"))
    declared: list[ArtifactKind | None] = []
    for step in definition.steps:
        if step.step_type != "loop":
            continue
        inner = step.config["steps"]
        assert isinstance(inner, list)
        revise = next(s["dispatch"] for s in inner if "dispatch" in s)
        kind = revise.get(ARTIFACT_KEY)
        declared.append(ArtifactKind(kind) if kind is not None else None)
    assert declared == loop_kinds


@pytest.mark.asyncio
async def test_loop_revise_dispatch_stamps_its_artifact(tmp_path: Path) -> None:
    """The real P4 loop shape: a plain dispatch revises the design and gets stamped."""
    from squadron.documents.frontmatter import read_frontmatter
    from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
    from squadron.pipeline.state import StateManager
    from tests.pipeline.conftest import phase_artifact_cf_client

    run_id = StateManager(runs_dir=tmp_path).init_run("slice", {"slice": "215"})
    design_path = tmp_path / "215-slice.stub.md"
    dispatch_mock = _dispatch_writer(design_path, "---\ndocType: slice-design\n---\n\nbody\n")
    pipeline = make_pipeline(
        [
            StepConfig(
                step_type="loop",
                name="revise-design",
                config={
                    "max": 3,
                    "until": "action.success",
                    "steps": [{"dispatch": {"name": "revise", ARTIFACT_KEY: "design"}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {"slice": "215"},
        resolver=MagicMock(),
        cf_client=phase_artifact_cf_client(215, "215-slice.stub.md", "215-tasks.stub.md"),
        cwd=str(tmp_path),
        run_id=run_id,
        runs_dir=tmp_path,
        _action_registry=phase_action_registry(dispatch_mock),
    )

    assert result.status == ExecutionStatus.COMPLETED
    frontmatter = read_frontmatter(design_path)
    assert frontmatter is not None
    assert frontmatter["revision_number"] == 1
