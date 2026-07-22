"""Tests for the metrology config keys (T12/T13).

Covers registration (types/defaults) and that the two behavior-affecting keys
are actually read: ``metrology.project_id`` by the identity fallback and
``metrology.store_dir`` by store-dir resolution.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from squadron.config.keys import CONFIG_KEYS
from squadron.metrology.identity import derive_project_id
from squadron.metrology.models import ProjectIdSource
from squadron.metrology.store import resolve_store_dir


class TestKeyRegistration:
    def test_all_three_keys_present_with_types(self) -> None:
        assert CONFIG_KEYS["metrology.store_dir"].type_ is str
        assert CONFIG_KEYS["metrology.sample_budget"].type_ is int
        assert CONFIG_KEYS["metrology.project_id"].type_ is str

    def test_defaults(self) -> None:
        assert CONFIG_KEYS["metrology.store_dir"].default is None
        assert CONFIG_KEYS["metrology.project_id"].default is None
        # A small non-zero ceiling — never zero (which would refuse all writes).
        budget_default = CONFIG_KEYS["metrology.sample_budget"].default
        assert isinstance(budget_default, int) and budget_default > 0


class TestKeysAreRead:
    def test_project_id_read_by_identity_fallback(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.project_id": "recorded/id"})
        pid = derive_project_id(str(repo_no_remote))
        assert pid.value == "recorded/id"
        assert pid.source == ProjectIdSource.RECORDED

    def test_store_dir_redirects_resolution(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        custom = repo_no_remote / "custom-store"
        write_project_config(repo_no_remote, {"metrology.store_dir": str(custom)})
        resolved = resolve_store_dir(cwd=str(repo_no_remote))
        assert resolved == custom

    def test_store_dir_unset_falls_back_to_default(self, repo_no_remote: Path) -> None:
        resolved = resolve_store_dir(cwd=str(repo_no_remote))
        assert resolved == Path.home() / ".config" / "squadron" / "metrology"
