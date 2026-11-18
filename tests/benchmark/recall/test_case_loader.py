"""Case-file loader and location derivation (slice 430 D1, D8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.recall.case_models import CaseFileError, derive_locations, load_case_file
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError, SubprocessRunner
from tests.benchmark.recall.fixtures.bug_repo.build import BUG_FILE, BuiltBugRepo
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed, ok

MINIMAL = """\
name: demo
kind: code
repo: ~/source/repos/demo
host_repo: owner/demo
distribution: demo
base: "aaaa"
head: "bbbb"
status: checked
bugs:
  - id: B1
    description: d
    proof: [{proof}]
    original_review: missed
{extras}"""


def _write(tmp_path: Path, proof: str = "abc123", extras: str = "", **replace: str) -> Path:
    text = MINIMAL.format(proof=proof, extras=extras)
    for old, new in replace.items():
        text = text.replace(old, new)
    path = tmp_path / "case.yaml"
    path.write_text(text)
    return path


def test_derived_locations_equal_fix_commit_files(bug_repo: BuiltBugRepo) -> None:
    spec = load_case_file(bug_repo.case_file)
    bugs = derive_locations(bug_repo.case_file, spec, SubprocessRunner(), timeout=30)
    assert [loc.file for loc in bugs[0].locations] == [BUG_FILE]


def test_extras_appended_after_derived(tmp_path: Path) -> None:
    extras = "    extra_locations:\n      - file: src/x.py\n        reason: cited by hits\n"
    path = _write(tmp_path, extras=extras)
    runner = ScriptedRunner(lambda call: ok(call.argv, "src/a.py\nsrc/b.py\n"))
    bugs = derive_locations(path, load_case_file(path), runner, timeout=5)
    assert [loc.file for loc in bugs[0].locations] == ["src/a.py", "src/b.py", "src/x.py"]
    assert runner.calls[0].argv == ("git", "show", "--name-only", "--format=", "abc123")
    assert runner.calls[0].cwd == str(Path("~/source/repos/demo").expanduser())
    assert load_case_file(path).repo == "~/source/repos/demo"


def test_issue_proof_without_extras_refused(tmp_path: Path) -> None:
    with pytest.raises(CaseFileError, match="issue proof but no extra_locations"):
        load_case_file(_write(tmp_path, proof='"#12"'))


def test_issue_proof_with_extras_derives_no_git(tmp_path: Path) -> None:
    extras = "    extra_locations:\n      - file: src/x.py\n        reason: from the issue\n"
    path = _write(tmp_path, proof='"#12"', extras=extras)
    runner = ScriptedRunner(lambda call: failed(call.argv))
    bugs = derive_locations(path, load_case_file(path), runner, timeout=5)
    assert [loc.file for loc in bugs[0].locations] == ["src/x.py"]
    assert runner.calls == []


@pytest.mark.parametrize(
    ("replace", "message"),
    [
        ({"status: checked": "status: maybe"}, "status"),
        ({"original_review: missed": "original_review: unsure"}, "original_review"),
        ({"distribution: demo\n": ""}, "distribution"),
        ({'base: "aaaa"': "base: 1234"}, "quoted string"),
    ],
)
def test_schema_refusals(tmp_path: Path, replace: dict[str, str], message: str) -> None:
    with pytest.raises(CaseFileError, match=message):
        load_case_file(_write(tmp_path, **replace))


def test_extra_without_reason_refused(tmp_path: Path) -> None:
    with pytest.raises(CaseFileError, match="without a reason"):
        load_case_file(_write(tmp_path, extras="    extra_locations:\n      - file: src/x.py\n"))


def test_git_show_failure_names_commit(tmp_path: Path) -> None:
    path = _write(tmp_path)
    runner = ScriptedRunner(lambda call: failed(call.argv, stderr="bad object abc123"))
    with pytest.raises(CaseFileError, match="proof commit abc123 failed"):
        derive_locations(path, load_case_file(path), runner, timeout=5)


def test_git_show_timeout_names_commit(tmp_path: Path) -> None:
    path = _write(tmp_path)

    def hang(call: RunnerCall) -> ProcessResult:
        raise ProcessTimedOutError(call.argv, call.timeout)

    with pytest.raises(CaseFileError, match="proof commit abc123 timed out"):
        derive_locations(path, load_case_file(path), ScriptedRunner(hang), timeout=5)
