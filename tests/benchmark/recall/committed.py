"""The committed case files, set lists and hand-run results, loaded with no git (slice 430).

Proof-commit file lists come from ``fixtures/proof_files.json`` through a scripted runner,
so tests that need the real cases in a temp store run without the source repos.
"""

from __future__ import annotations

import dataclasses
import json
import re
from functools import cache
from pathlib import Path

from squadron.benchmark.recall.hand_run_import import build_import_plan
from squadron.benchmark.recall.import_writer import write_import_plan
from squadron.benchmark.recall.kinds import KindContext, get_kind
from squadron.benchmark.recall.recall_services import RecallServices
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.recall_case_models import RealBugCase
from tests.benchmark.recall.support import PROJECT, fake_services, invoke_recall
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed, ok

REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCE = REPO_ROOT / "project-documents" / "user" / "reference"
CASES_DIR = REFERENCE / "review-recall-cases"
SETS_FILE = REFERENCE / "review-recall-sets.md"
RESULTS_DIR = REFERENCE / "review-recall-results"
RECIPES_DIR = REFERENCE / "review-recall-recipes"
OVERRIDES_FILE = REFERENCE / "review-recall-overrides.yaml"
PROOF_FILES = Path(__file__).parent / "fixtures" / "proof_files.json"

_SET_SECTION = re.compile(r"^##\s+(?P<name>\S+)\s*$\n+```[^\n]*\n(?P<body>.*?)^```", re.M | re.S)


def case_files() -> list[Path]:
    return sorted(CASES_DIR.glob("*.yaml"))


def parse_sets(text: str) -> dict[str, list[str]]:
    """``## <set>`` headings, each followed by a fenced block of case-file names."""
    sets: dict[str, list[str]] = {}
    for match in _SET_SECTION.finditer(text):
        lines = [line.strip() for line in match["body"].splitlines()]
        sets[match["name"]] = [line for line in lines if line]
    return sets


def proof_runner() -> ScriptedRunner:
    """Answers ``git show --name-only`` from the captured proof file lists."""
    proof_files: dict[str, list[str]] = json.loads(PROOF_FILES.read_text(encoding="utf-8"))

    def handler(call: RunnerCall) -> ProcessResult:
        if "show" not in call.argv:
            # The lock's own `ps` checks run for real; only proof-commit reads are faked.
            return SubprocessRunner().run(call.argv, cwd=call.cwd, timeout=call.timeout)
        files = proof_files.get(call.argv[-1])
        if files is None:
            return failed(call.argv, stderr=f"no captured files for {call.argv[-1]}")
        return ok(call.argv, stdout="\n".join(files) + "\n")

    return ScriptedRunner(handler)


@cache
def committed_cases() -> dict[str, RealBugCase]:
    """Every committed case, by case-file name, validated through its kind."""
    context = KindContext(proof_runner(), 1.0, PROJECT)
    return {path.name: get_kind("code").validate(path, context) for path in case_files()}


def load_committed_sets(store: RecallRecordStore) -> None:
    """Write the 17 cases and the four committed sets into *store*."""
    cases = committed_cases()
    for case in cases.values():
        store.write_case(case)
    for name, members in parse_sets(SETS_FILE.read_text(encoding="utf-8")).items():
        store.write_case_set(name, [cases[member].case_id for member in members])


def cases_by_hand_id() -> dict[str, RealBugCase]:
    found: dict[str, RealBugCase] = {}
    for case in committed_cases().values():
        assert case.hand_run_id is not None, case.name
        found[case.hand_run_id] = case
    return found


def add_committed_sets(services: RecallServices) -> None:
    """Run ``cases add`` for each committed set list, as the walkthrough does (fake git)."""
    sets = parse_sets(SETS_FILE.read_text(encoding="utf-8"))
    for name, members in sets.items():
        paths = [str(CASES_DIR / member) for member in members]
        result = invoke_recall(services, "cases", "add", *paths, "--set", name)
        assert result.exit_code == 0, (result.output, result.exception)


def imported_services(tmp_path: Path) -> RecallServices:
    """A temp store holding the committed cases and sets plus the full hand-run import."""
    services = dataclasses.replace(fake_services(tmp_path, proof_runner()), repo_root=REPO_ROOT)
    add_committed_sets(services)
    case_set = services.store.resolve_set("real-bugs")
    cases = [services.store.get_case(case_id) for case_id in case_set.case_ids]
    plan = build_import_plan(
        RESULTS_DIR, [c for c in cases if c is not None], "real-bugs@v1", OVERRIDES_FILE
    )
    write_import_plan(services.store, plan)
    return services
