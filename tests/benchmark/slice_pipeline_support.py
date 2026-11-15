"""The slice-case replay world of the fixture project (slice 426, Tasks 26 and 41).

Real: sandboxes, git, cf registration under the scrubbed home, uv installs, pytest and the
stores. Scripted: the runner's one ``sq run P6 <index> --producer-only`` call, which
``ScriptedProducer`` answers the way the producer would (commit, no commit), and no model is
called. The transcript source reports one transcript file with one harmless command.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.case_runners import ReplaySandbox
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.benchmark.replay_deps import ReplayOneDeps
from squadron.benchmark.replay_one import replay_one
from squadron.benchmark.slice_runner import SliceCaseRunner, candidate_from_case
from squadron.benchmark.transcripts import ToolCall, TranscriptResult
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.metrology.benchmark_replay_models import CaseDrop, ImplementationReplay
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.pipeline.state import StateManager, runs_dir_under, state_file_name
from squadron.providers.base import ProfileName
from squadron.replay.cf_registration import CfRegistration
from tests.benchmark.test_slice_build_end_to_end import Setup
from tests.stats.producer_support import action, run, step, usage

#: A profile that carries no login: the sandbox home gets nothing from the real home.
PROFILE = ProfileName.LOCAL.value
BENCHMARK_ID = "bench-0123456789abcdef"
SQ_PATH = "/scripted/sq"
CAPS = Caps(run_cap_usd=20.0, per_replay_cap_usd=8.0, per_replay_source="--max-cost-per-replay")
GIT_TIMEOUT_S = 120
CONFIG_REFERENCE = BenchConfig("opus", "m-opus", PROFILE, None)
CONFIG_BREAKING = BenchConfig("sol", "m-sol", PROFILE, None)
CONFIG_SILENT = BenchConfig("astra", "m-astra", PROFILE, None)
CONFIGS = (CONFIG_REFERENCE, CONFIG_BREAKING, CONFIG_SILENT)
BREAKING_LINE = "    return left + right  # broken\n"
RUN_STEP = "implement"


class ScriptedTranscript:
    """A transcript source for a scripted producer: one transcript file, one harmless command
    (the leak scan treats a transcript with no tool calls as unscannable)."""

    def read(self, home: Path) -> TranscriptResult:
        return TranscriptResult(tool_calls=(ToolCall("Bash", {"command": "pytest -q"}),), files_read=1)


class ScriptedProducer:
    """Answers the runner's ``sq run P6`` call by alias: apply the reference diff and commit,
    break one test and commit, or commit nothing. It runs git under the scrubbed environment
    the runner passed, and writes the run state where the producer's home keeps it."""

    def __init__(self, repo: Path, fork: str, tip: str) -> None:
        self._runner = SubprocessRunner()
        self._repo, self._fork, self._tip = repo, fork, tip
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(
        self, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None
    ) -> ProcessResult:
        assert env is not None
        self.calls.append((list(argv), cwd))
        alias = argv[argv.index("-m") + 1]
        record_id = argv[argv.index("--run-id") + 1]
        actions = [action("dispatch", model="m", profile=PROFILE, usage_record=usage(cost=0.4))]
        if alias == CONFIG_REFERENCE.alias:
            self._apply_reference(cwd, env)
        elif alias == CONFIG_BREAKING.alias:
            self._break_a_test(cwd, env)
        if alias != CONFIG_SILENT.alias:
            actions.append(action("commit"))
        self._write_state(record_id, actions, Path(env["HOME"]))
        return ProcessResult(tuple(argv), 0, "", "")

    def _git(self, tree: Path, env: Mapping[str, str], *args: str, stdin: str | None = None) -> None:
        result = self._runner.run(
            ["git", *args], cwd=str(tree), timeout=GIT_TIMEOUT_S, env=env, stdin=stdin, replace_env=True
        )
        assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"

    def _apply_reference(self, tree: Path, env: Mapping[str, str]) -> None:
        reference = subprocess.run(
            ["git", "-C", str(self._repo), "diff", "--binary", self._fork, self._tip],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self._git(tree, env, "apply", "--index", stdin=reference)
        self._git(tree, env, "commit", "-q", "-m", "scripted: reference change")

    def _break_a_test(self, tree: Path, env: Mapping[str, str]) -> None:
        source = tree / "src" / "calc.py"
        lines = source.read_text().splitlines(keepends=True)
        sub_return = lines.index("    return left - right\n")
        lines[sub_return] = BREAKING_LINE
        source.write_text("".join(lines))
        self._git(tree, env, "add", "src/calc.py")
        self._git(tree, env, "commit", "-q", "-m", "scripted: breaking change")

    def _write_state(self, record_id: str, actions: list[dict[str, object]], home: Path) -> None:
        state = run(record_id, [step(RUN_STEP, RUN_STEP, actions)], pipeline="P6")
        path = runs_dir_under(home) / state_file_name(record_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.model_dump(mode="json")))


@dataclass(frozen=True)
class SliceWorld:
    """The built case, the replays of the three configs, and the doubles behind them."""

    setup: Setup
    case: BenchmarkCase
    producer: ScriptedProducer
    replays: Mapping[str, ImplementationReplay]

    def replays_with_ids(self) -> list[tuple[str, ImplementationReplay]]:
        """The stored replays with their record ids."""
        return self.setup.records.replays_for(BENCHMARK_ID)


def replay_world(tmp_path: Path) -> SliceWorld:
    """Build the fixture project's slice case, then replay it once under each of three configs."""
    setup = Setup(tmp_path)
    case = setup.case_of(setup.build())
    history = setup.history
    producer = ScriptedProducer(history.repo, history.code.landing.fork, history.code.landing.tip)
    process_runner = SubprocessRunner()
    slice_runner = SliceCaseRunner(
        sq_path=SQ_PATH,
        invoker=producer,
        runner=process_runner,
        registration_for=lambda env: CfRegistration(process_runner, env),
        qualify_deps=setup.deps.qualify,
        candidate_for=lambda found: candidate_from_case(found, setup.deps.ranges),
    )
    deps = _replay_deps(tmp_path, setup, slice_runner, process_runner)
    replays: dict[str, ImplementationReplay] = {}
    for config in CONFIGS:
        result = replay_one(case, config, 0, deps)
        assert not isinstance(result, CaseDrop), f"{config.alias} was dropped: {result}"
        replays[config.alias] = result
    return SliceWorld(setup, case, producer, replays)


def _replay_deps(
    tmp_path: Path, setup: Setup, slice_runner: SliceCaseRunner, process_runner: SubprocessRunner
) -> ReplayOneDeps:
    def leak_rules(sandbox: ReplaySandbox, case: BenchmarkCase) -> LeakRules:
        return build_leak_rules(
            tree=sandbox.tree,
            home=sandbox.home,
            output_dir=sandbox.output_dir,
            real_home=Path.home(),
            repo_root=setup.history.repo,
            install_location=tmp_path / "site-packages",
            uv_cache=tmp_path / "uv-cache",
            distribution_name="squadron-ai",
            host_owner="owner",
            host_repo="repo",
        )

    return ReplayOneDeps(
        benchmark_id=BENCHMARK_ID,
        case_set="e2e-slices",
        case_set_version=1,
        caps=CAPS,
        keep=False,
        git_timeout_s=GIT_TIMEOUT_S,
        sandbox_factory=lambda case: setup.deps.qualify.sandbox_factory(case.start_sha),
        runners=lambda kind: slice_runner if kind is CaseKind.SLICE else None,
        store=setup.records,
        state_reader_for=lambda runs_dir: StateManager(runs_dir=runs_dir),
        transcript_sources=lambda profile: ScriptedTranscript(),
        leak_rules_for=leak_rules,
        config_ref_for=lambda config: ProducerConfigRef(
            alias=config.alias,
            model=config.model,
            profile=config.profile,
            effort_sent=None,
            tool_use=True,
        ),
        process_runner=process_runner,
        clock=lambda: datetime.now(UTC),
    )
