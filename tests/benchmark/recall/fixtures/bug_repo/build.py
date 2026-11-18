"""Build the recall fixture bug repo and its case file (slice 430, walkthrough step 5).

``build(out_dir)`` makes ``out_dir/repo/``: a git repo with a base commit, a buggy head
commit and a later fix commit, plus ``out_dir/case.yaml`` naming that repo, base, head and
one bug B1 proven by the fix commit. Run as a script with no argument, ``out_dir`` is this
script's own folder. Uses only the standard library, so it runs outside the test suite.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CASE_NAME = "fixture-bug-repo"
HOST_REPO = "fixture-owner/bug-repo"
DISTRIBUTION = "bug-repo"
BUG_FILE = "src/bug_repo/clamp.py"
_IDENTITY = ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid")
_PYPROJECT = '[project]\nname = "bug-repo"\nversion = "0.1.0"\n'
_BASE_SOURCE = (
    '"""Numeric helpers."""\n\n\n'
    "def average(values: list[float]) -> float:\n"
    "    return sum(values) / len(values)\n"
)
_BUGGY = (
    '"""Clamp a value into a range."""\n\n\n'
    "def clamp(value: float, low: float, high: float) -> float:\n"
    "    return max(low, min(value, low))\n"
)
_FIXED = _BUGGY.replace("min(value, low)", "min(value, high)")


@dataclass(frozen=True)
class BuiltBugRepo:
    repo: Path
    case_file: Path
    base: str
    head: str
    fix: str


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    completed = subprocess.run(
        ["git", *_IDENTITY, *args], cwd=repo, capture_output=True, text=True, check=True, env=env
    )
    return completed.stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for relative, text in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _case_yaml(repo: Path, base: str, head: str, fix: str) -> str:
    return (
        f"name: {CASE_NAME}\n"
        "kind: code\n"
        f"repo: {repo}\n"
        f"host_repo: {HOST_REPO}\n"
        f"distribution: {DISTRIBUTION}\n"
        f"base: {base}\n"
        f"head: {head}\n"
        "status: verified\n"
        "bugs:\n"
        "  - id: B1\n"
        '    description: "clamp bounds the value by low twice, so it never respects high"\n'
        f"    proof: [{fix}]\n"
        "    original_review: missed\n"
        'notes: "Fixture repo built by tests/benchmark/recall/fixtures/bug_repo/build.py."\n'
    )


def build(out_dir: Path) -> BuiltBugRepo:
    """Create ``out_dir/repo`` and ``out_dir/case.yaml``, replacing any earlier build."""
    repo = out_dir / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    base = _commit(
        repo,
        {
            "pyproject.toml": _PYPROJECT,
            "src/bug_repo/__init__.py": "",
            "src/bug_repo/stats.py": _BASE_SOURCE,
        },
        "init",
    )
    head = _commit(repo, {BUG_FILE: _BUGGY}, "feat: add clamp")
    fix = _commit(repo, {BUG_FILE: _FIXED}, "fix: clamp respects the upper bound")
    case_file = out_dir / "case.yaml"
    case_file.write_text(_case_yaml(repo, base, head, fix), encoding="utf-8")
    return BuiltBugRepo(repo=repo, case_file=case_file, base=base, head=head, fix=fix)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    built = build(target)
    print(f"built {built.repo} and {built.case_file}")
