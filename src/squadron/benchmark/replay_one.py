"""One (case, config, sample) replay: sandbox, producer, diff, leak scan, record (slice 424).

Every collaborator is injected through ``ReplayOneDeps``, so tests run no model and no git
outside fixtures. A replay ends in one of three ways: a written ``ImplementationReplay``
(any producer outcome, harness failures included, so resume skips it), a ``CaseDrop`` when
re-qualification rejects the case (nothing is dispatched and nothing is written), or a
``ReplayStoreError`` when something after the producer cannot be stored. In that last case the
sandbox is kept and no record is written, and the caller stops the benchmark (D10).

The diff is stored as UTF-8 text from ``git diff --binary``: binary content is base85, but a
text file holding invalid UTF-8 is recorded with replacement characters (``TEXT_DECODING``).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from squadron.benchmark.adapter import EnvironmentResolutionError
from squadron.benchmark.bench_plan import BenchConfig, config_key, replay_record_id
from squadron.benchmark.case_runners import CaseKindRunner, ReplaySandbox
from squadron.benchmark.instruction_files import instruction_files
from squadron.benchmark.leak_scan import scan
from squadron.benchmark.replay_deps import ReplayOneDeps, ReplayStoreError, store_failure
from squadron.benchmark.replay_outcome import ProducerClassification
from squadron.benchmark.replay_records import (
    ReplayFields,
    absence_and_detail,
    build_record,
    environment_failed_record,
    write_record,
)
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
)
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    QualificationOutcome,
)
from squadron.metrology.benchmark_replay_models import (
    CaseDrop,
    DiffRef,
    ImplementationReplay,
    LeakScanResult,
)
from squadron.metrology.errors import MetrologyStoreError
from squadron.pipeline.state import STATE_READ_ERRORS, RunState, runs_dir_under
from squadron.pipeline.text_tail import tail_text
from squadron.providers.base import ProfileName
from squadron.replay.history_free_sandbox import SandboxError

__all__ = ["ReplayOneDeps", "ReplayStoreError", "replay_one"]

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ProducerRun:
    classification: ProducerClassification
    head_before: str
    head_after: str
    wall_seconds: float


def _git(deps: ReplayOneDeps, tree: Path, *args: str) -> ProcessResult | str:
    """The finished ``git`` call, or why it could not finish (missing, timed out, no cwd)."""
    try:
        return deps.process_runner.run(["git", *args], cwd=str(tree), timeout=deps.git_timeout_s)
    except (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError) as exc:
        return f"git {' '.join(args)}: {exc}"


def _head(deps: ReplayOneDeps, tree: Path) -> str | None:
    result = _git(deps, tree, "rev-parse", "HEAD")
    if isinstance(result, str):
        _logger.error("cannot read HEAD in %s: %s", tree, result)
        return None
    if result.returncode != 0:
        _logger.error("cannot read HEAD in %s: %s", tree, tail_text(result.stderr))
        return None
    return result.stdout.strip()


def _diff_ref(deps: ReplayOneDeps, sandbox: ReplaySandbox, case: BenchmarkCase) -> DiffRef:
    result = _git(deps, sandbox.tree, "diff", "--binary", case.start_sha, "HEAD")
    if isinstance(result, str):
        raise store_failure(sandbox, result)
    if result.returncode != 0:
        message = f"git diff exited {result.returncode}: {tail_text(result.stderr)}"
        raise store_failure(sandbox, message)
    try:
        return deps.store.diffs.put(result.stdout.encode("utf-8"))
    except MetrologyStoreError as exc:
        raise store_failure(sandbox, f"diff sidecar write failed: {exc}") from exc


def _read_state(deps: ReplayOneDeps, sandbox: ReplaySandbox, record_id: str) -> RunState | None:
    reader = deps.state_reader_for(runs_dir_under(sandbox.home))
    try:
        return reader.load(record_id)
    except FileNotFoundError:
        _logger.warning("replay %s left no run state", record_id)
    except STATE_READ_ERRORS as exc:
        _logger.warning("replay %s left an unreadable run state: %s", record_id, exc)
    return None


def _requalified(
    deps: ReplayOneDeps, runner: CaseKindRunner, case: BenchmarkCase, sandbox: ReplaySandbox
) -> CaseDrop | None:
    """A ``CaseDrop`` when *case* no longer qualifies in this environment, else ``None``."""
    digest = sandbox.identity.identity_digest
    key = (case.case_id, digest)
    if key not in deps.requalify_cache:
        deps.requalify_cache[key] = runner.requalify(case, sandbox.identity)
    verdict = deps.requalify_cache[key]
    if isinstance(verdict, CandidateRejection):
        return CaseDrop(case_id=case.case_id, reason=verdict, environment_digest=digest)
    if verdict.outcome is QualificationOutcome.QUALIFIED:
        return None
    reason = verdict.rejection or verdict.detail or verdict.outcome.value
    return CaseDrop(case_id=case.case_id, reason=reason, environment_digest=digest)


def _produce(
    deps: ReplayOneDeps,
    runner: CaseKindRunner,
    case: BenchmarkCase,
    config: BenchConfig,
    sandbox: ReplaySandbox,
    record_id: str,
) -> _ProducerRun | str:
    """Run the producer and classify it; a string is why the sandbox could not be used."""
    head_before = _head(deps, sandbox.tree)
    if head_before is None:
        return "cannot read HEAD in the sandbox before the producer"
    began = time.monotonic()
    process = runner.run(case, config, sandbox, deps.caps, record_id)
    wall_seconds = time.monotonic() - began
    head_after = _head(deps, sandbox.tree)
    if head_after is None:
        raise store_failure(sandbox, "cannot read HEAD in the sandbox after the producer")
    state = _read_state(deps, sandbox, record_id)
    classification = runner.classify(case, process, state, head_before, head_after)
    return _ProducerRun(classification, head_before, head_after, wall_seconds)


def _leak_result(
    deps: ReplayOneDeps, case: BenchmarkCase, config: BenchConfig, sandbox: ReplaySandbox
) -> LeakScanResult:
    if config.profile is None:
        raise ValueError(f"model alias '{config.alias}' resolves to no provider profile")
    source = deps.transcript_sources(ProfileName(config.profile))
    if source is None:
        raise RuntimeError(f"profile {config.profile} has no transcript source; planning refuses it")
    return scan(source, sandbox.home, deps.leak_rules_for(sandbox, case))


def _finish(
    deps: ReplayOneDeps,
    runner: CaseKindRunner,
    case: BenchmarkCase,
    config: BenchConfig,
    sample: int,
    record_id: str,
    sandbox: ReplaySandbox,
    produced: _ProducerRun,
    files: tuple[tuple[str, str], ...],
) -> ImplementationReplay:
    classification = produced.classification
    moved = produced.head_after != produced.head_before
    leak = _leak_result(deps, case, config, sandbox)
    diff = _diff_ref(deps, sandbox, case) if moved else None
    absence, detail = absence_and_detail(classification, leak)
    ref = deps.config_ref_for(config).model_copy(update={"effort_sent": classification.effort_sent})
    fields = ReplayFields(
        config=ref,
        outcome=classification.outcome,
        absence=absence,
        failure_detail=detail,
        leak=leak,
        diff=diff,
        commit_sha=produced.head_after if moved else None,
        environment=sandbox.identity,
        prompt=classification.prompt,
        instruction_files=files,
        cost_usd=classification.cost_usd,
        turns=classification.turns,
        wall_seconds=produced.wall_seconds,
    )
    record = build_record(deps, runner, case, sample, record_id, fields)
    write_record(deps, record_id, record, sandbox)
    return record


def replay_one(
    case: BenchmarkCase, config: BenchConfig, sample: int, deps: ReplayOneDeps
) -> ImplementationReplay | CaseDrop:
    """Replay *case* under *config* once; see the module docstring for the three endings."""
    runner = deps.runners(case.kind)
    if runner is None:
        raise RuntimeError(f"no case runner for kind '{case.kind.value}'; planning refuses it")
    record_id = replay_record_id(deps.benchmark_id, case.case_id, config_key(config), sample)
    try:
        with deps.sandbox_factory(case) as sandbox:
            if (drop := _requalified(deps, runner, case, sandbox)) is not None:
                return drop
            files = instruction_files(sandbox.tree)
            produced = _produce(deps, runner, case, config, sandbox, record_id)
            if isinstance(produced, str):
                return environment_failed_record(
                    deps, runner, case, config, sample, record_id, produced
                )
            record = _finish(deps, runner, case, config, sample, record_id, sandbox, produced, files)
            if deps.keep:
                sandbox.keep()
            return record
    except (EnvironmentResolutionError, SandboxError) as exc:
        return environment_failed_record(deps, runner, case, config, sample, record_id, str(exc))
