"""Shared builders for recall tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from click.testing import Result
from typer.testing import CliRunner

from squadron.benchmark.recall.live_services import LiveRunServices
from squadron.benchmark.recall.recall_services import RecallServices
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.cli.commands.benchmark_recall import build_recall_app
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.recall_case_models import BugLocation, KnownBug, OriginalReview
from squadron.metrology.store import MetrologyStore

PROJECT = ProjectId(value="recall-test", source=ProjectIdSource.RECORDED)


def make_bug(bug_id: str = "B1", file: str = "src/a.py") -> KnownBug:
    return KnownBug(
        id=bug_id,
        description="wrong thing",
        proof=("abc123",),
        original_review=OriginalReview.MISSED,
        locations=(BugLocation(file=file),),
    )


def case_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project_id": PROJECT,
        "name": "demo-1",
        "kind": "code",
        "repo": "~/source/repos/demo",
        "host_repo": "owner/demo",
        "distribution": "demo",
        "base": "b" * 40,
        "head": "h" * 40,
        "status": "checked",
        "bugs": (make_bug("B1"), make_bug("B2", "src/b.py")),
    }
    fields.update(overrides)
    return fields


FIXED_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def fake_services(tmp_path: Path, runner: ProcessRunner | None = None) -> RecallServices:
    """Services over a temp store and benchmark root; real git unless *runner* is given."""
    store = RecallRecordStore(MetrologyStore(tmp_path / "store"), clock=lambda: FIXED_NOW)
    return RecallServices(
        repo_root=tmp_path,
        store=store,
        process_runner=runner if runner is not None else SubprocessRunner(),
        bench_root=tmp_path / "bench",
        clock=lambda: FIXED_NOW,
        read_config=lambda key: None,
        fetch_timeout=30.0,
        project_id=lambda: PROJECT,
        stage_resolver=ImportOnlyResolver(),
        live=unused_live_services(),
    )


def _unused(*_args: object, **_kwargs: object) -> Any:
    raise AssertionError("this test does not run stages; pass live services for run")


def unused_live_services() -> LiveRunServices:
    """Live services for tests that never reach ``run``: every collaborator fails loudly."""
    return LiveRunServices(
        harness_env={},
        sq_path=_unused,
        auth_check=_unused,
        auth_timeout=_unused,
        leak_checker=_unused,
        leak_judgeable=_unused,
        config_for=_unused,
        sandboxes=_unused,
    )


def invoke_recall(services: RecallServices, *args: str) -> Result:
    """Run ``sq benchmark recall ARGS`` against *services*."""
    app = build_recall_app(lambda _repo: services)
    return CliRunner().invoke(app, list(args))
