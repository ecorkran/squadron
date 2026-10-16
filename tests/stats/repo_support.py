"""A throwaway git repo with controlled author dates, for the history-reading stats tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path


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
