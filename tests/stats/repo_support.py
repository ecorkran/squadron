"""A throwaway git repo with controlled author dates, for the history-reading stats tests."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.review.git_utils import run_git


class StatsRepo:
    """Builds commits with exact paths and author dates; hermetic config comes from conftest."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str, date: str | None = None) -> str:
        env = dict(os.environ)
        if date is not None:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        done = subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=True, env=env
        )
        return done.stdout.strip()

    def commit(self, subject: str, files: Mapping[str, str | None], date: str) -> str:
        """Commit ``files`` (``None`` deletes the path) authored at ISO ``date``; returns the sha."""
        for relative, content in files.items():
            path = self.root / relative
            if content is None:
                self.git("rm", "-q", relative)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.git("add", relative)
        self.git("commit", "-q", "--allow-empty", "-m", subject, date=date)
        return self.git("rev-parse", "HEAD")

    def move(self, subject: str, source: str, target: str, date: str) -> str:
        (self.root / target).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", source, target)
        self.git("commit", "-q", "-m", subject, date=date)
        return self.git("rev-parse", "HEAD")

    def branch(self, name: str) -> None:
        self.git("checkout", "-q", "-b", name)

    def checkout(self, name: str) -> None:
        self.git("checkout", "-q", name)

    def merge(self, name: str, subject: str, date: str) -> str:
        self.git("merge", "-q", "--no-ff", "-m", subject, name, date=date)
        return self.git("rev-parse", "HEAD")

    def blob(self, sha: str, path: str) -> str:
        return self.git("rev-parse", f"{sha}:{path}")


class CountingRunner:
    """The real ``run_git`` with a call log, so a test can assert D6's `2 + V` call count."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        self.calls.append(args)
        return run_git(args, cwd=cwd)


def write_run_file(runs_dir: Path, run_id: str, slice_index: int | str, cost_usd: float = 0.5) -> None:
    """A completed one-dispatch run file for ``slice_index`` whose dispatch cost ``cost_usd``."""
    usage = UsageRecord(
        model="m",
        alias=None,
        profile="sdk",
        effort=None,
        turns=2,
        duration_seconds=3.0,
        usage=TokenUsage(prompt=100, completion=10),
        cost_usd=cost_usd,
        cost_basis=CostBasis.PROVIDER,
    ).to_dict()
    action = {"success": True, "action_type": "dispatch", "outputs": {}, "metadata": {"usage": usage}}
    state = {
        "schema_version": 5,
        "run_id": run_id,
        "pipeline": "p4",
        "params": {"slice": slice_index},
        "started_at": "2026-10-04T10:00:00+00:00",
        "updated_at": "2026-10-04T11:00:00+00:00",
        "status": "completed",
        "completed_steps": [
            {
                "step_name": "design",
                "step_type": "phase",
                "status": "completed",
                "completed_at": "2026-10-04T10:30:00+00:00",
                "action_results": [action],
            }
        ],
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(state))
