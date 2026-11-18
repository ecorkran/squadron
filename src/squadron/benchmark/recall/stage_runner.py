"""One stage call: a scrubbed subprocess in the case sandbox, giving a ``StageEntry`` (D6, D8).

The call runs ``sq`` by absolute path with cwd = the sandbox and a 421 scrubbed environment
holding only the alias profile's credentials. The output file is the signal: no file means
the call never reached the model (``harness_failure``); a timeout or an unparseable file is
the config's (``config_failure``). The scrubbed home is kept until the entry is stored, so
an orphan output found on resume can still be leak-scanned; the caller removes it.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.benchmark.recall.kinds import get_kind
from squadron.benchmark.recall.run_plan import PendingStage
from squadron.benchmark.recall.scoring import reviewer_output
from squadron.benchmark.recall.stage_ingest import (
    STDERR_TAIL_CHARS,
    IngestContext,
    empty_comb_entry,
    failure_entry,
    ingest_output,
    read_comb_input,
    write_comb_input,
)
from squadron.benchmark.sandbox import RECALL_HOMES, RECALL_OUT
from squadron.benchmark.scrubbed_env import CredentialGrant, MissingCredentialError, ScrubbedEnvironment
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.metrology.recall_run_models import (
    RecallFinding,
    RecallLeakVerdict,
    RecallRun,
    StageEntry,
    StageKind,
    StageOutcome,
    chain_key,
    comb_slot,
)
from squadron.providers.base import ProfileName

COMB_TEMPLATE = "comb"


@dataclass(frozen=True)
class StageContext:
    """What the leak checker needs about one finished call."""

    stage: PendingStage
    profile: ProfileName
    sandbox: Path
    home: Path
    output_dir: Path


class LeakChecker(Protocol):
    def check(self, context: StageContext) -> RecallLeakVerdict: ...


@dataclass(frozen=True)
class StageDeps:
    runner: ProcessRunner
    bench_root: Path
    sq_path: Path
    harness_env: Mapping[str, str]
    review_timeout: float
    leak_checker: LeakChecker
    ingest: IngestContext


@dataclass(frozen=True)
class StagePaths:
    output: Path
    comb_input: Path
    #: The sandbox tree the call ran in, so an orphan is scanned against that tree.
    sandbox_record: Path
    home_root: Path
    home_id: str

    @property
    def home(self) -> Path:
        return self.home_root / f"{self.home_id}.home"


def stage_paths(stage: PendingStage, bench_root: Path) -> StagePaths:
    """Deterministic paths, so a resumed run finds an earlier call's output and home."""
    out_dir = bench_root / RECALL_OUT / stage.record_id
    return StagePaths(
        output=out_dir / f"{stage.file_key}.json",
        comb_input=out_dir / f"{stage.file_key}.input.json",
        sandbox_record=out_dir / f"{stage.file_key}.sandbox",
        home_root=bench_root / RECALL_HOMES,
        home_id=f"{stage.record_id}-{stage.file_key[:16]}",
    )


def comb_input_findings(stage: PendingStage, run: RecallRun) -> list[RecallFinding]:
    """The parent's kept findings: the scored review findings, or the previous comb's KEEPs."""
    review = run.reviews.get(stage.review_key)
    if review is None:
        return []
    parents = tuple(
        run.combs[comb_slot(stage.review_key, chain_key(stage.chain[:depth]))]
        for depth in range(1, len(stage.chain))
    )
    return list(reviewer_output(stage.reviewer, review, parents).lower)


def run_stage(stage: PendingStage, run: RecallRun, sandbox: Path, deps: StageDeps) -> StageEntry:
    """Make the call for *stage* and return its entry (never raises for a D8 failure mode)."""
    paths = stage_paths(stage, deps.bench_root)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    findings: list[RecallFinding] | None = None
    if stage.kind is StageKind.COMB:
        findings = comb_input_findings(stage, run)
        if not findings:
            return empty_comb_entry(stage, deps.ingest)
        write_comb_input(paths.comb_input, findings)
    profile = ProfileName(str(stage.config.profile))
    environment = ScrubbedEnvironment(
        paths.home_root, paths.home_id, CredentialGrant.for_profiles([profile]), deps.harness_env
    )
    try:
        variables = environment.variables(())
    except MissingCredentialError as exc:
        return failure_entry(stage, StageOutcome.HARNESS_FAILURE, str(exc), deps.ingest)
    environment.cleanup()  # a home left by an earlier, unrecorded call
    environment.prepare()
    paths.output.unlink(missing_ok=True)
    paths.sandbox_record.write_text(str(sandbox), encoding="utf-8")
    try:
        result = deps.runner.run(
            _argv(stage, paths, deps.sq_path),
            cwd=str(sandbox),
            timeout=deps.review_timeout,
            env=variables,
            replace_env=True,
        )
    except (ProcessNotFoundError, ProcessCwdNotFoundError) as exc:
        return failure_entry(
            stage, StageOutcome.HARNESS_FAILURE, f"could not start: {exc}", deps.ingest
        )
    except ProcessTimedOutError:
        leak = deps.leak_checker.check(
            StageContext(stage, profile, sandbox, environment.home, paths.output.parent)
        )
        reason = f"timed out after {deps.review_timeout:g}s"
        return failure_entry(stage, StageOutcome.CONFIG_FAILURE, reason, deps.ingest, leak)
    leak = deps.leak_checker.check(
        StageContext(stage, profile, sandbox, environment.home, paths.output.parent)
    )
    if not paths.output.is_file():
        tail = result.stderr.strip()[-STDERR_TAIL_CHARS:]
        reason = f"exit {result.returncode} without output file: {tail}"
        return failure_entry(stage, StageOutcome.HARNESS_FAILURE, reason, deps.ingest, leak)
    return ingest_output(stage, paths.output, findings, leak, deps.ingest)


def ingest_orphan(stage: PendingStage, deps: StageDeps) -> StageEntry | None:
    """An output file with no entry (a crash after the call): its entry, or ``None`` if absent.

    The leak scan runs against the sandbox the call ran in (recorded before the call) while
    the call's scrubbed home is still present; otherwise ``None`` is returned so the caller
    repeats the call.
    """
    paths = stage_paths(stage, deps.bench_root)
    if not (paths.output.is_file() and paths.home.is_dir() and paths.sandbox_record.is_file()):
        return None
    sandbox = Path(paths.sandbox_record.read_text(encoding="utf-8").strip())
    findings = read_comb_input(paths.comb_input) if stage.kind is StageKind.COMB else None
    profile = ProfileName(str(stage.config.profile))
    leak = deps.leak_checker.check(
        StageContext(stage, profile, sandbox, paths.home, paths.output.parent)
    )
    return ingest_output(stage, paths.output, findings, leak, deps.ingest)


def remove_home(stage: PendingStage, bench_root: Path) -> None:
    """Remove the call's scrubbed home once its entry is stored."""
    shutil.rmtree(stage_paths(stage, bench_root).home, ignore_errors=True)


def _argv(stage: PendingStage, paths: StagePaths, sq_path: Path) -> list[str]:
    if stage.kind is StageKind.REVIEW:
        return get_kind(stage.case.kind).review_argv(stage.case, stage.alias, sq_path, paths.output)
    return [
        str(sq_path), "benchmark", "recall", "_stage", "--template", COMB_TEMPLATE,
        "--input", str(paths.comb_input), "--output", str(paths.output),
        "--model", stage.alias, "--diff", stage.case.base,
    ]  # fmt: skip
