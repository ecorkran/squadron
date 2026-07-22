"""Tests for project-identity derivation (T2/T3).

Covers URL normalization across remote-form variants, the recorded-id
fallback, explicit failure when neither source is present, and the
remote-absent / non-repo fall-through (git-remote-absent failure-mode row).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.metrology.errors import MetrologyIdentityError
from squadron.metrology.identity import derive_project_id, normalize_remote_url
from squadron.metrology.models import ProjectIdSource


class TestNormalizeRemoteUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/manta/example-repo.git",
            "https://github.com/manta/example-repo",
            "git@github.com:manta/example-repo.git",
            "git@github.com:manta/example-repo",
            "https://user:token@github.com/manta/example-repo.git",
            "ssh://git@github.com/manta/example-repo.git",
            "https://github.com/manta/example-repo/",
        ],
    )
    def test_variants_collapse_to_one_canonical_id(self, url: str) -> None:
        assert normalize_remote_url(url) == "github.com/manta/example-repo"


class TestDeriveProjectId:
    def test_remote_url_yields_remote_sourced_id(self, repo_with_remote: Path) -> None:
        pid = derive_project_id(str(repo_with_remote))
        assert pid.value == "github.com/manta/example-repo"
        assert pid.source == ProjectIdSource.REMOTE

    def test_no_remote_with_recorded_id_returns_recorded(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.project_id": "acme/widget"})
        pid = derive_project_id(str(repo_no_remote))
        assert pid.value == "acme/widget"
        assert pid.source == ProjectIdSource.RECORDED

    def test_no_remote_no_recorded_id_raises_actionable(self, repo_no_remote: Path) -> None:
        with pytest.raises(MetrologyIdentityError) as exc:
            derive_project_id(str(repo_no_remote))
        # Actionable: names the config fix, never a path-derived fallback.
        assert "metrology.project_id" in str(exc.value)

    def test_non_repo_falls_through_to_recorded(
        self,
        non_repo_dir: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        # git absent-as-remote (non-repo) must not crash — it falls through.
        write_project_config(non_repo_dir, {"metrology.project_id": "plain/dir"})
        pid = derive_project_id(str(non_repo_dir))
        assert pid.value == "plain/dir"
        assert pid.source == ProjectIdSource.RECORDED

    def test_non_repo_no_recorded_id_raises(self, non_repo_dir: Path) -> None:
        with pytest.raises(MetrologyIdentityError):
            derive_project_id(str(non_repo_dir))
