"""File-set resolution tests (slice 400, D4)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.metrology.errors import SnapshotIntegrityError
from squadron.metrology.snapshot import files as files_module
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.files import (
    effective_exclusions,
    group_by_language,
    resolve_files,
)
from squadron.metrology.snapshot_models import Measurement, SnapshotMetric, SourceLanguage
from tests.metrology.snapshot.conftest import SnapshotRepoFactory


class StubAdapter:
    language = SourceLanguage.PYTHON
    metrics: frozenset[SnapshotMetric] = frozenset()

    def __init__(self, *conventions: str) -> None:
        self.convention_exclusions = tuple(conventions)

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        raise AssertionError("not called")


class TestResolveFiles:
    def test_untracked_files_never_appear(self, snapshot_git_repo: SnapshotRepoFactory) -> None:
        repo = snapshot_git_repo({"a.py": "x = 1\n"})
        (repo / "untracked.py").write_text("y = 1\n", encoding="utf-8")
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "dep.js").write_text("z\n", encoding="utf-8")

        assert resolve_files(repo, []) == ["a.py"]

    def test_exclusion_removes_every_file_under_it_at_any_depth(
        self, snapshot_git_repo: SnapshotRepoFactory
    ) -> None:
        repo = snapshot_git_repo(
            {
                "commands/analysis/top.py": "a\n",
                "commands/analysis/deep/er/nested.py": "b\n",
                "commands/other.py": "c\n",
                "src/keep.py": "d\n",
            }
        )

        assert resolve_files(repo, ["commands/analysis/**"]) == [
            "commands/other.py",
            "src/keep.py",
        ]

    def test_convention_patterns_remove_tracked_matches(
        self, snapshot_git_repo: SnapshotRepoFactory
    ) -> None:
        repo = snapshot_git_repo(
            {
                "src/types.d.ts": "a\n",
                "src/real.ts": "b\n",
                "node_modules/pkg/index.ts": "c\n",
                "pkg/node_modules/deep/x.ts": "d\n",
            }
        )

        assert resolve_files(repo, ["**/*.d.ts", "**/node_modules/**"]) == ["src/real.ts"]

    def test_path_with_space_and_non_ascii_survives_the_nul_split(
        self, snapshot_git_repo: SnapshotRepoFactory
    ) -> None:
        repo = snapshot_git_repo({"my dir/naïve file.py": "x = 1\n", "ünï/ç.py": "y = 1\n"})

        assert resolve_files(repo, []) == ["my dir/naïve file.py", "ünï/ç.py"]

    def test_git_returning_none_raises_and_logs_error(
        self,
        snapshot_git_repo: SnapshotRepoFactory,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        repo = snapshot_git_repo({"a.py": "x = 1\n"})

        def run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
            return None

        monkeypatch.setattr(files_module, "run_git", run_git)

        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(SnapshotIntegrityError, match="git ls-files"),
        ):
            resolve_files(repo, [])

        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_git_failure_raises_instead_of_returning_an_empty_set(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(SnapshotIntegrityError):
            resolve_files(tmp_path, [])  # not a git repo: ls-files exits non-zero

        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestEffectiveExclusions:
    def test_sorted_and_deduplicated_union(self) -> None:
        result = effective_exclusions(
            ["z/**", "a/**", "a/**"], [StubAdapter("**/*.d.ts", "a/**"), StubAdapter("**/dist/**")]
        )

        assert result == ["**/*.d.ts", "**/dist/**", "a/**", "z/**"]


class TestGroupByLanguage:
    def test_extensions_map_to_languages(self) -> None:
        grouped = group_by_language(
            ["a.ts", "b.tsx", "c.mts", "d.cts", "e.mjs", "f.sh", "g.py", "README.md", "Makefile"]
        )

        assert grouped == {
            SourceLanguage.TYPESCRIPT: ["a.ts", "b.tsx", "c.mts", "d.cts"],
            SourceLanguage.JAVASCRIPT: ["e.mjs"],
            SourceLanguage.SHELL: ["f.sh"],
            SourceLanguage.PYTHON: ["g.py"],
        }
