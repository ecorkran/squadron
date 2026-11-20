"""Builders for the live-run tests: stages, deps, scripted ``sq`` outputs (slice 430)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from squadron.benchmark.recall.run_plan import PendingStage, expand_pending
from squadron.benchmark.recall.stage_ingest import IngestContext
from squadron.benchmark.recall.stage_runner import StageContext, StageDeps
from squadron.core.models import Effort
from squadron.core.process_runner import ProcessResult
from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import RecallLeakVerdict, StageConfig, StageKind
from squadron.recipes.recipe import Recipe
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.recall.support import FIXED_NOW
from tests.benchmark.support import RunnerCall, ScriptedRunner, ok

PROFILE = "openrouter"
API_KEY_ENV = "OPENROUTER_API_KEY"


def live_config_for(alias: str, kind: StageKind) -> tuple[StageConfig, Effort | None]:
    config = StageConfig(
        model=f"vendor/{alias}",
        profile=PROFILE,
        template_hash=f"live-{kind.value}",
        tool_use=True,
        max_output_tokens=None,
    )
    return config, None


def pending_for(case: RealBugCase, recipe: Recipe, run_index: int = 1) -> list[PendingStage]:
    return expand_pending([recipe], [case], [run_index], {}, live_config_for)


@dataclass
class StubLeakChecker:
    verdict: RecallLeakVerdict = RecallLeakVerdict.CONFINED
    seen: list[StageContext] = field(default_factory=list[StageContext])

    def check(self, context: StageContext) -> RecallLeakVerdict:
        self.seen.append(context)
        return self.verdict


def harness_env(tmp_path: Path) -> dict[str, str]:
    real_home = tmp_path / "real-home"
    real_home.mkdir(exist_ok=True)
    return {"HOME": str(real_home), "PATH": os.environ["PATH"], API_KEY_ENV: "test-key"}


def stage_deps(
    tmp_path: Path,
    runner: ScriptedRunner,
    leak: StubLeakChecker | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> StageDeps:
    store_dir = tmp_path / "store"
    return StageDeps(
        runner=runner,
        bench_root=tmp_path / "bench",
        sq_path=Path("/opt/sq"),
        harness_env=env if env is not None else harness_env(tmp_path),
        review_timeout=timeout,
        leak_checker=leak or StubLeakChecker(),
        ingest=IngestContext(
            sidecar=ContentSidecars(store_dir, SidecarKind.REVIEWS),
            case_set="s@v1",
            clock=lambda: FIXED_NOW,
        ),
    )


def output_arg(argv: tuple[str, ...]) -> Path:
    """The output path of a review (``--output-path``) or ``_stage`` (``--output``) argv."""
    flag = "--output-path" if "--output-path" in argv else "--output"
    return Path(argv[argv.index(flag) + 1])


def review_document(findings: list[dict[str, Any]], cost: float = 0.01) -> dict[str, Any]:
    return {"findings": findings, "effort": "high", "cost_usd": cost, "cost_basis": "alias_pricing"}


def sq_finding(index: int, location: str = "src/app.py:3", severity: str = "CONCERN") -> dict[str, Any]:
    return {
        "severity": severity,
        "title": f"finding {index}",
        "description": f"text {index}",
        "location": location,
        "category": "correctness",
        "raw_category": None,
    }


Writer = Callable[[RunnerCall], None]


def writing_runner(
    write: Writer, result: Callable[[RunnerCall], ProcessResult] | None = None
) -> ScriptedRunner:
    """A runner that runs *write* for every call (to produce output files), then answers ok."""

    def handler(call: RunnerCall) -> ProcessResult:
        write(call)
        return result(call) if result else ok(call.argv)

    return ScriptedRunner(handler)


def write_json(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


PLAN_PROFILE = "openai-oauth"


def plan_config_for(alias: str, kind: StageKind) -> tuple[StageConfig, Effort | None]:
    """Aliases starting ``codex`` are plan-billed (Codex profile); others as ``live_config_for``."""
    config, effort = live_config_for(alias, kind)
    if alias.startswith("codex"):
        config = config.model_copy(update={"profile": PLAN_PROFILE})
    return config, effort


@dataclass
class FakeSandboxes:
    """Yields a fixed tree, or raises ``SandboxError`` for named cases; records enter/exit."""

    tree: Path
    failures: dict[str, str] = field(default_factory=dict[str, str])
    events: list[str] = field(default_factory=list[str])

    def open(self, case: RealBugCase) -> AbstractContextManager[Path]:
        return self._open(case)

    @contextmanager
    def _open(self, case: RealBugCase) -> Iterator[Path]:
        if case.name in self.failures:
            raise SandboxError(self.failures[case.name])
        self.events.append(f"enter {case.name}")
        try:
            yield self.tree
        finally:
            self.events.append(f"exit {case.name}")
