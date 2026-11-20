"""End to end on the fixture repo: real sandbox and subprocess, a scripted ``sq`` (slice 430).

The scripted ``sq`` writes a review output and, in its scrubbed ``HOME``, a transcript of
the tool calls it "made". The alias ``leaky`` reads the case's source checkout by absolute
path, so its entry is recorded ``leaked`` and the report drops it, counting the drop.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from squadron.benchmark.auth_check import AuthAnswer, AuthCheckResult
from squadron.benchmark.recall.kinds import KindContext, registered_kind
from squadron.benchmark.recall.leak_check import LeakInputs, TranscriptLeakChecker
from squadron.benchmark.recall.live_services import LiveRunServices
from squadron.benchmark.recall.recall_services import RecallServices
from squadron.benchmark.recall.recipe_dirs import RECIPES_DIR
from squadron.benchmark.recall.run_loop import KindSandboxFactory
from squadron.benchmark.recall.run_plan import expand_pending
from squadron.benchmark.recall.scoring_select import StageIdentity
from squadron.benchmark.recall.stage_ingest import IngestContext
from squadron.benchmark.recall.stage_runner import StageDeps, run_stage
from squadron.benchmark.transcripts import ToolCall, TranscriptResult
from squadron.config.keys import BENCHMARK_REVIEW_TIMEOUT_KEY
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.recall_case_models import RealBugCase, RecallCaseKind
from squadron.metrology.recall_run_models import RecallLeakVerdict, RecallRun, StageKind, StageOutcome
from squadron.providers.base import ProfileName
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.fixtures.bug_repo.build import BUG_FILE, BuiltBugRepo
from tests.benchmark.recall.scoring_support import make_case
from tests.benchmark.recall.stage_support import harness_env, live_config_for
from tests.benchmark.recall.support import fake_services, invoke_recall

TRANSCRIPT = "transcript.json"
SCRIPT = """#!{python}
import json, os, sys
argv = sys.argv[1:]
out = argv[argv.index("--output-path") + 1]
alias = argv[argv.index("--model") + 1]
repo = {repo!r}
calls = [{{"tool": "Read", "input": {{"file_path": os.path.join(os.getcwd(), {bug!r})}}}}]
if alias == "leaky":
    calls.append({{"tool": "Bash", "input": {{"command": "git -C " + repo + " log -p"}}}})
with open(os.path.join(os.environ["HOME"], {transcript!r}), "w") as handle:
    json.dump(calls, handle)
finding = {{"severity": "CONCERN", "title": "wrong total", "description": "sums twice",
           "location": {bug!r} + ":3", "category": "correctness", "raw_category": None}}
with open(out, "w") as handle:
    json.dump({{"findings": [finding], "effort": None, "cost_usd": 0.01}}, handle)
"""


class HomeTranscript:
    """Reads the tool calls the scripted ``sq`` wrote into its scrubbed home."""

    def read(self, home: Path) -> TranscriptResult:
        path = home / TRANSCRIPT
        if not path.is_file():
            return TranscriptResult(tool_calls=(), files_read=0)
        calls = json.loads(path.read_text())
        return TranscriptResult(
            tool_calls=tuple(ToolCall(c["tool"], c["input"]) for c in calls), files_read=1
        )


class LiveIdentities:
    def resolve(self, alias: str, stage_kind: StageKind) -> StageIdentity | None:
        config, _ = live_config_for(alias, stage_kind)
        return StageIdentity(config.config_key, None)


def _sq_script(tmp_path: Path, repo: Path) -> Path:
    script = tmp_path / "bin" / "sq"
    script.parent.mkdir()
    script.write_text(
        SCRIPT.format(python=sys.executable, repo=str(repo), bug=BUG_FILE, transcript=TRANSCRIPT)
    )
    script.chmod(0o755)
    return script


def _services(tmp_path: Path, bug_repo: BuiltBugRepo) -> RecallServices:
    sq = _sq_script(tmp_path, bug_repo.repo)
    leak = TranscriptLeakChecker(
        LeakInputs(
            real_home=tmp_path / "real-home",
            install_location=tmp_path / "site",
            uv_cache=tmp_path / "uv",
        ),
        source_for=lambda profile: HomeTranscript(),
    )
    live = LiveRunServices(
        harness_env=harness_env(tmp_path),
        sq_path=lambda: str(sq),
        auth_check=lambda aliases, *rest: [
            AuthCheckResult(ProfileName.OPENROUTER, aliases[0], AuthAnswer.YES, 0, "")
        ],
        auth_timeout=lambda: 5.0,
        leak_checker=lambda runner: leak,
        leak_judgeable=lambda profile: True,
        config_for=live_config_for,
        sandboxes=lambda context, root: KindSandboxFactory(context, root / "recall-sandboxes", "e2e"),
    )
    base = fake_services(tmp_path, SubprocessRunner())
    timeout = {BENCHMARK_REVIEW_TIMEOUT_KEY: 60}
    return dataclasses.replace(
        base, live=live, stage_resolver=LiveIdentities(), read_config=lambda key: timeout.get(key)
    )


def _recipe(tmp_path: Path, alias: str) -> str:
    path = tmp_path / f"{alias}.yaml"
    path.write_text(f"name: {alias}\nreviewers: [{alias}]\n", encoding="utf-8")
    return str(path)


def test_two_reviews_with_verdicts_and_a_leak_dropped_from_report(
    tmp_path: Path, bug_repo: BuiltBugRepo
) -> None:
    services = _services(tmp_path, bug_repo)
    added = invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "fixture")
    assert added.exit_code == 0, added.output
    common = ("--set", "fixture", "--max-cost", "1", "--call-cost", "0.01")
    clean = invoke_recall(services, "run", "--recipe", _recipe(tmp_path, "rev"), "--runs", "2", *common)
    assert clean.exit_code == 0, clean.output
    leaky = invoke_recall(services, "run", "--recipe", _recipe(tmp_path, "leaky"), *common)
    assert leaky.exit_code == 0, leaky.output
    runs = services.store.list_runs()
    entries = {(r.run_index, e.alias): e for r in runs for e in r.reviews.values()}
    assert entries[(1, "rev")].leak is RecallLeakVerdict.NO_LEAK_DETECTED
    assert entries[(2, "rev")].leak is RecallLeakVerdict.NO_LEAK_DETECTED
    assert entries[(1, "leaky")].leak is RecallLeakVerdict.LEAKED
    assert all(e.outcome is StageOutcome.OK and len(e.findings) == 1 for e in entries.values())
    assert not list((services.bench_root / "recall-sandboxes").glob("*"))  # sandboxes removed
    report = invoke_recall(
        services, "report", "--set", "fixture", "--recipe", _recipe(tmp_path, "rev"),
        "--recipe", _recipe(tmp_path, "leaky"), "--runs", "1",
    )  # fmt: skip
    assert report.exit_code == 0, report.output
    assert "| rev | 1 | 1 |" in report.output
    assert "Dropped (leak): 1 (leaked 1)" in report.output
    bench_dir = tmp_path / RECIPES_DIR
    bench_dir.mkdir(parents=True)
    (bench_dir / "rev.yaml").write_text("name: rev\nreviewers: [rev]\n", encoding="utf-8")
    by_name = invoke_recall(services, "report", "--set", "fixture", "--recipe", "rev", "--runs", "1")
    assert by_name.exit_code == 0, by_name.output
    assert "| rev | 1 | 1 |" in by_name.output


class StubKind:
    """A second case kind: no git sandbox, its own review command."""

    def __init__(self, tree: Path, sq: Path) -> None:
        self.tree = tree
        self.sq = sq

    def validate(self, case_file: Path, context: KindContext) -> RealBugCase:
        raise AssertionError("not used")

    def open_sandbox(
        self, case: RealBugCase, context: KindContext, root: Path, sandbox_id: str
    ) -> AbstractContextManager[Path]:
        return nullcontext(self.tree)

    def review_argv(self, case: RealBugCase, alias: str, sq_path: Path, out_path: Path) -> list[str]:
        return [str(self.sq), "--model", alias, "--output-path", str(out_path)]


def test_a_stub_kind_registered_in_the_registry_runs_one_stage(
    tmp_path: Path, bug_repo: BuiltBugRepo
) -> None:
    services = _services(tmp_path, bug_repo)
    tree = tmp_path / "stub-tree"
    tree.mkdir()
    (tmp_path / "stub").mkdir()
    sq = _sq_script(tmp_path / "stub", bug_repo.repo)
    stub_case = make_case("stub-case")
    with registered_kind(RecallCaseKind.CODE, StubKind(tree, sq)):
        stage = expand_pending(
            [Recipe(name="r", reviewers=("rev",))], [stub_case], [1], {}, live_config_for
        )[0]
        deps = StageDeps(
            runner=SubprocessRunner(),
            bench_root=services.bench_root,
            sq_path=Path("/unused"),
            harness_env=services.live.harness_env,
            review_timeout=60,
            leak_checker=services.live.leak_checker(SubprocessRunner()),
            ingest=IngestContext(services.store.reviews, "s@v1", services.clock),
        )
        sandboxes = KindSandboxFactory(services.kind_context(), services.bench_root, "stub")
        with sandboxes.open(stub_case) as sandbox:
            entry = run_stage(stage, RecallRun(case_id=stub_case.case_id, run_index=1), sandbox, deps)
    assert sandbox == tree
    assert entry.outcome is StageOutcome.OK and len(entry.findings) == 1
