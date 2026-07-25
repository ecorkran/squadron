"""Tests for the metrology config keys (T12/T13).

Covers registration (types/defaults) and that the two behavior-affecting keys
are actually read: ``metrology.project_id`` by the identity fallback and
``metrology.store_dir`` by store-dir resolution.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from squadron.config.keys import CONFIG_KEYS
from squadron.config.manager import get_config
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

    def test_report_keys_present_with_types_and_defaults(self) -> None:
        floor_key = CONFIG_KEYS["metrology.min_evidence_n"]
        bucket_key = CONFIG_KEYS["metrology.trend_bucket"]
        assert floor_key.type_ is int
        assert isinstance(floor_key.default, int) and floor_key.default > 0
        assert bucket_key.type_ is str
        assert bucket_key.default == "month"

    def test_calibration_keys_present_with_float_types_and_defaults(self) -> None:
        graduate_key = CONFIG_KEYS["metrology.graduate_match_rate"]
        tighten_key = CONFIG_KEYS["metrology.tighten_match_rate"]
        residual_key = CONFIG_KEYS["metrology.residual_sample_rate"]
        assert graduate_key.type_ is float
        assert isinstance(graduate_key.default, float)
        assert tighten_key.type_ is float
        assert isinstance(tighten_key.default, float)
        assert residual_key.type_ is float
        assert isinstance(residual_key.default, float)


class TestReportKeysAreRead:
    def test_min_evidence_n_reads_back_as_int(self, repo_no_remote: Path) -> None:
        value = get_config("metrology.min_evidence_n", cwd=str(repo_no_remote))
        assert isinstance(value, int)

    def test_trend_bucket_reads_back_as_str(self, repo_no_remote: Path) -> None:
        value = get_config("metrology.trend_bucket", cwd=str(repo_no_remote))
        assert isinstance(value, str)

    def test_min_evidence_n_project_override_honored(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.min_evidence_n": 10})
        value = get_config("metrology.min_evidence_n", cwd=str(repo_no_remote))
        assert value == 10

    def test_trend_bucket_project_override_honored(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.trend_bucket": "week"})
        value = get_config("metrology.trend_bucket", cwd=str(repo_no_remote))
        assert value == "week"

    def test_graduate_match_rate_reads_back_as_float(self, repo_no_remote: Path) -> None:
        value = get_config("metrology.graduate_match_rate", cwd=str(repo_no_remote))
        assert isinstance(value, float)

    def test_tighten_match_rate_reads_back_as_float(self, repo_no_remote: Path) -> None:
        value = get_config("metrology.tighten_match_rate", cwd=str(repo_no_remote))
        assert isinstance(value, float)

    def test_residual_sample_rate_reads_back_as_float(self, repo_no_remote: Path) -> None:
        value = get_config("metrology.residual_sample_rate", cwd=str(repo_no_remote))
        assert isinstance(value, float)

    def test_graduate_match_rate_project_override_honored(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.graduate_match_rate": 0.95})
        value = get_config("metrology.graduate_match_rate", cwd=str(repo_no_remote))
        assert value == 0.95

    def test_tighten_match_rate_project_override_honored(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.tighten_match_rate": 0.5})
        value = get_config("metrology.tighten_match_rate", cwd=str(repo_no_remote))
        assert value == 0.5

    def test_residual_sample_rate_project_override_honored(
        self,
        repo_no_remote: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        write_project_config(repo_no_remote, {"metrology.residual_sample_rate": 0.25})
        value = get_config("metrology.residual_sample_rate", cwd=str(repo_no_remote))
        assert value == 0.25


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
