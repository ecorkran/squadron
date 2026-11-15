"""Per-kind case runners: the seam between ``replay_one`` and a kind of case (slice 424 D5).

``replay_one`` calls only this protocol, so adding a kind (426's slice cases) means writing a
runner and registering it, not editing the replay driver. A case set holding a kind with no
registered runner is refused at planning.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.fix_case_candidate import issue_number
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify import qualification_for, qualify_candidate
from squadron.benchmark.qualify_types import QualifyDeps
from squadron.benchmark.replay_outcome import ProducerClassification, classify_producer_run
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    FixQualification,
)
from squadron.metrology.slice_case_models import SliceQualification
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName

ISSUE_FILE_NAME = "issue.md"
FIX_PIPELINE = "fix"
ISSUE_FILE_PARAM = "issue-file"
COMMIT_TO_PARAM = "commit-to"
COMMIT_TO_CURRENT = "current"
#: The branch a producer commits to in its sandbox: the start commit's tree is detached.
PRODUCER_BRANCH = "benchmark-replay"
#: The one step of a producer-only ``fix`` run; the replay record names it.
FIX_PRODUCER_STEP = "fix"


class ReplaySandbox(Protocol):
    """What a replay uses of its sandbox; ``BenchmarkSandbox`` satisfies it.

    ``replay_one`` and the case runners depend on this, not on the concrete sandbox, so tests
    run them against a directory-backed double.
    """

    @property
    def tree(self) -> Path: ...

    @property
    def home(self) -> Path: ...

    @property
    def output_dir(self) -> Path: ...

    @property
    def identity(self) -> EnvironmentIdentity: ...

    def keep(self) -> None: ...

    def producer_env(self, profile: ProfileName, tools: Sequence[str] = ()) -> dict[str, str]: ...

    def checkout_branch(self, name: str) -> None: ...


class SqInvoker(Protocol):
    """Runs ``sq`` as a child. ``env`` is the child's whole environment (see ``run_sq_subprocess``)."""

    def __call__(
        self, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None
    ) -> ProcessResult: ...


#: What re-qualifying a case gives: a stored or fresh qualification record of its kind, or the
#: rejection that ends it (fix cases only; slice cases record their rejection).
Requalification = FixQualification | SliceQualification | CandidateRejection

#: What running the producer returns: the finished ``sq`` process.
ProducerRun = ProcessResult


class CaseKindRunner(Protocol):
    def requalify(self, case: BenchmarkCase, environment: EnvironmentIdentity) -> Requalification:
        """The case's qualification in *environment*, or the rejection that ends it."""
        ...

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProducerRun:
        """Run the producer for *case* in *sandbox* under *config*; never grades."""
        ...

    @property
    def pipeline(self) -> str:
        """The pipeline name a replay record of this kind carries."""
        ...

    @property
    def producer_step(self) -> str:
        """The step name a replay record of this kind carries."""
        ...

    def classify(
        self,
        case: BenchmarkCase,
        process: ProcessResult,
        state: RunState | None,
        head_before: str,
        head_after: str,
    ) -> ProducerClassification:
        """How the finished producer run ended: its outcome, absence class and usage."""
        ...


_RUNNERS: dict[CaseKind, CaseKindRunner] = {}


def register_case_runner(kind: CaseKind, runner: CaseKindRunner) -> None:
    """Make *runner* the runner for cases of *kind*."""
    _RUNNERS[kind] = runner


def case_runner_for(kind: CaseKind) -> CaseKindRunner | None:
    """The runner for *kind*, ``None`` when none is registered."""
    return _RUNNERS.get(kind)


class FixCaseRunner:
    """Runs ``sq run fix`` producer-only on a fix case, and re-qualifies it from 422's store.

    Every collaborator is injected: the absolute path of the installed ``sq`` (resolved once at
    harness start, because the scrubbed ``PATH`` cannot reach it), the invoker, 422's
    ``QualifyDeps`` and the function that rebuilds a candidate from a case.
    """

    pipeline = FIX_PIPELINE
    producer_step = FIX_PRODUCER_STEP

    def __init__(
        self,
        *,
        sq_path: str,
        invoker: SqInvoker,
        qualify_deps: QualifyDeps,
        candidate_for: Callable[[BenchmarkCase], FixCandidate],
    ) -> None:
        self._sq_path = sq_path
        self._invoker = invoker
        self._deps = qualify_deps
        self._candidate_for = candidate_for

    def requalify(self, case: BenchmarkCase, environment: EnvironmentIdentity) -> Requalification:
        existing = qualification_for(case, environment, self._deps.store, self._deps.repeats)
        if existing is not None:
            return existing
        return qualify_candidate(self._candidate_for(case), self._deps).record

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProducerRun:
        number = issue_number(case)
        if number is None:
            raise ValueError(
                f"fix case {case.case_id} has no readable issue ref: {case.provenance.source_ref!r}"
            )
        if config.profile is None:
            raise ValueError(f"model alias '{config.alias}' resolves to no provider profile")
        (sandbox.output_dir / ISSUE_FILE_NAME).write_bytes(case.task_text.encode("utf-8"))
        sandbox.checkout_branch(PRODUCER_BRANCH)
        argv = [
            self._sq_path, "run", FIX_PIPELINE, str(number),
            "-m", config.alias,
            "--producer-only",
            "--max-cost", str(caps.per_replay_cap_usd),
            "-p", f"{ISSUE_FILE_PARAM}={ISSUE_FILE_NAME}",
            "-p", f"{COMMIT_TO_PARAM}={COMMIT_TO_CURRENT}",
            "--io-dir", str(sandbox.output_dir),
            "--run-id", record_id,
        ]  # fmt: skip
        env = sandbox.producer_env(ProfileName(config.profile))
        return self._invoker(argv, cwd=sandbox.tree, env=env)

    def classify(
        self,
        case: BenchmarkCase,
        process: ProcessResult,
        state: RunState | None,
        head_before: str,
        head_after: str,
    ) -> ProducerClassification:
        # The run must have used the frozen issue text, so its hash is part of the verdict.
        issue_sha256 = hashlib.sha256(case.task_text.encode("utf-8")).hexdigest()
        return classify_producer_run(process, state, head_before, head_after, issue_sha256)
