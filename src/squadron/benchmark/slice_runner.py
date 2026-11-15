"""The slice-case runner on 424's case-kind seam (slice 426 D8, D9).

``SliceCaseRunner.run`` registers the sandbox as a cf project inside the scrubbed home, then
runs the installed ``sq`` producer-only on ``P6``. Registration happens under the producer's
own environment, so cf reads and writes its registry in the scrubbed home: nothing is added
to the user's cf registry and no ``cf project rm`` is ever issued (removing the home removes
the project).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path

from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.case_runners import ProducerRun, ReplaySandbox, Requalification, SqInvoker
from squadron.benchmark.replay_outcome import ProducerClassification, classify_producer_run
from squadron.benchmark.slice_discovery import SliceCandidate, SliceRangeSource
from squadron.benchmark.slice_git import SliceHarnessError, run_git
from squadron.benchmark.slice_qualify import qualify_slice_candidate, slice_qualification_for
from squadron.benchmark.slice_qualify_run import parse_source_ref
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName
from squadron.replay.cf_registration import CfRegistration, CfRegistrationError
from squadron.replay.history_free_sandbox import SandboxError

_logger = logging.getLogger(__name__)

SLICE_PIPELINE = "P6"
#: The one step of a producer-only ``P6`` run; the replay record names it.
SLICE_PRODUCER_STEP = "implement"
#: cf is a node script, so the scrubbed ``PATH`` needs ``node`` as well as ``cf`` (Task 10 spike).
CF_TOOLS = ("cf", "node")
#: ``sq run --producer-only`` refuses a branch that does not parse as ``{index}-slice.{name}``,
#: so a detached tree is put on ``{index}-slice.`` + this + the sandbox id.
SLICE_BRANCH_SUFFIX = "benchmark-"

#: Builds the registration for one environment (the producer's, scrubbed home included).
RegistrationFactory = Callable[[Mapping[str, str]], CfRegistration]


def candidate_from_case(case: BenchmarkCase, ranges: SliceRangeSource) -> SliceCandidate:
    """The candidate a stored slice case came from, found again in the ``slice_ranges`` record."""
    index, after_sha = parse_source_ref(case)
    record = ranges.get_slice_ranges(case.project_id)
    if record is None:
        raise ValueError(f"no slice ranges are recorded for case {case.case_id}'s project")
    for landing in record.slices.get(index, ()):
        if landing.after_sha == after_sha:
            return SliceCandidate(case.project_id, index, landing)
    raise ValueError(f"slice {index} has no landing {after_sha[:12]} in the recorded ranges")


class SliceCaseRunner:
    """Runs ``sq run P6`` producer-only on a slice case, and re-qualifies it from 426's store.

    Every collaborator is injected: the installed ``sq`` by absolute path, the invoker, the
    registration factory, the process runner for git, and qualification's deps.
    """

    pipeline = SLICE_PIPELINE
    producer_step = SLICE_PRODUCER_STEP

    def __init__(
        self,
        *,
        sq_path: str,
        invoker: SqInvoker,
        runner: ProcessRunner,
        registration_for: RegistrationFactory,
        qualify_deps: SliceQualifyDeps,
        candidate_for: Callable[[BenchmarkCase], SliceCandidate],
    ) -> None:
        self._sq_path = sq_path
        self._invoker = invoker
        self._runner = runner
        self._registration_for = registration_for
        self._deps = qualify_deps
        self._candidate_for = candidate_for

    def requalify(self, case: BenchmarkCase, environment: EnvironmentIdentity) -> Requalification:
        existing = slice_qualification_for(
            self._deps.qualifications, case, environment, self._deps.repeats
        )
        if existing is not None:
            return existing
        return qualify_slice_candidate(self._candidate_for(case), self._deps).record

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProducerRun:
        index, _ = parse_source_ref(case)
        if config.profile is None:
            raise ValueError(f"model alias '{config.alias}' resolves to no provider profile")
        env = sandbox.producer_env(ProfileName(config.profile), CF_TOOLS)
        branch = self._branch(sandbox, index)
        try:
            self._registration_for(env).register(sandbox.tree, sandbox.tree.name, branch, index)
        except CfRegistrationError as exc:
            # The producer never ran, so replay_one records a harness absence, not the config's.
            _logger.exception(
                "cf registration failed for slice %d replay %s: %s", index, record_id, exc
            )
            raise SandboxError(str(exc)) from exc
        argv = [
            self._sq_path, "run", SLICE_PIPELINE, str(index),
            "-m", config.alias,
            "--producer-only",
            "--max-cost", str(caps.per_replay_cap_usd),
            "--run-id", record_id,
        ]  # fmt: skip
        return self._invoker(argv, cwd=sandbox.tree, env=env)

    def classify(
        self,
        case: BenchmarkCase,
        process: ProducerRun,
        state: RunState | None,
        head_before: str,
        head_after: str,
    ) -> ProducerClassification:
        # P6 has no frozen issue text to check; everything else is the fix classification.
        return classify_producer_run(process, state, head_before, head_after, None)

    def _branch(self, sandbox: ReplaySandbox, index: int) -> str:
        """The branch the tree is on, creating a slice branch when it is detached."""
        current = self._current_branch(sandbox.tree)
        if current:
            return current
        name = f"{index}-slice.{SLICE_BRANCH_SUFFIX}{sandbox.tree.name}"
        try:
            sandbox.checkout_branch(name)
        except SandboxError:
            _logger.exception("could not create branch %s for slice %d", name, index)
            raise
        return name

    def _current_branch(self, tree: Path) -> str:
        """``git branch --show-current`` in *tree*; empty for a detached HEAD."""
        try:
            return run_git(
                self._runner, tree, ["branch", "--show-current"], self._deps.git_timeout_s
            ).strip()
        except SliceHarnessError as exc:
            # ``run_git`` logged it; the tree cannot be used.
            raise SandboxError(str(exc)) from exc
