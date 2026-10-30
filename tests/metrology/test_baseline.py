"""prepare_baseline: every config check before anything runs, and the scope plan (slice 404)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.metrology.audit import AuditSkillError
from squadron.metrology.baseline import prepare_baseline
from squadron.metrology.errors import BaselinePreflightError, MetrologyIdentityError
from squadron.metrology.snapshot.contract import AdapterRegistry
from squadron.metrology.snapshot.files import resolve_files
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.take import take_snapshot
from squadron.metrology.snapshot_models import SnapshotMetric, SourceLanguage
from squadron.metrology.store import MetrologyStore
from tests.conftest import run_test_git
from tests.metrology.snapshot.builders import FakeAdapter
from tests.metrology.snapshot.conftest import FakeToolRunner

UserConfigWriter = Callable[[dict[str, object]], Path]

CONFIG: dict[str, object] = {
    "metrology.audit_model": "model-x",
    "metrology.audit_profile": "profile-x",
    "metrology.audit_run_cooldown_s": 0,
}


def _fake_registry() -> AdapterRegistry:
    return {
        SourceLanguage.PYTHON: FakeAdapter(
            SourceLanguage.PYTHON,
            frozenset({SnapshotMetric.FILE_LENGTH}),
            convention_exclusions=("build/**",),
        )
    }


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_success_plan_describes_head_identity_scope_and_config(
    audited_repo: Path, write_user_config: UserConfigWriter
) -> None:
    write_user_config({**CONFIG, "metrology.audit_variance_runs": 4})

    plan = prepare_baseline(audited_repo, default_registry(), profile=None, model=None)

    assert plan.head_sha == _head(audited_repo)
    assert plan.project_id.value == "github.com/manta/example-repo"
    assert plan.file_count == 1
    assert plan.byte_count == len("# fixture\n")
    assert (plan.runs, plan.cooldown_s) == (4, 0)
    assert (plan.profile, plan.model) == ("profile-x", "model-x")
    assert plan.project_path == audited_repo


def test_explicit_profile_and_model_override_config(
    audited_repo: Path, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)

    plan = prepare_baseline(audited_repo, default_registry(), profile="cli-profile", model="cli-model")

    assert (plan.profile, plan.model) == ("cli-profile", "cli-model")


def test_scope_matches_the_file_set_the_snapshot_measures(
    audited_repo: Path, write_user_config: UserConfigWriter, tmp_path: Path
) -> None:
    write_user_config({**CONFIG, "metrology.snapshot_exclude": "vendor/**"})
    for relative in ("a.py", "vendor/v.py", "build/b.py", "docs/notes.md"):
        target = audited_repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
    run_test_git(audited_repo, "add", "-A")
    run_test_git(audited_repo, "commit", "-q", "-m", "more files")
    registry = _fake_registry()

    plan = prepare_baseline(audited_repo, registry, profile=None, model=None)
    store = MetrologyStore(store_dir=tmp_path / "store")
    snapshot = take_snapshot(audited_repo, registry, FakeToolRunner(), store)

    assert plan.exclusions == snapshot.exclusions
    assert plan.file_count == len(resolve_files(audited_repo, snapshot.exclusions))
    assert plan.file_count == 3, "README.md, a.py, docs/notes.md survive the exclusions"
    assert sum(entry.file_count for entry in snapshot.languages) <= plan.file_count


@pytest.mark.parametrize(
    ("config", "expected_text"),
    [
        ({"metrology.audit_profile": "p"}, "metrology.audit_model"),
        (
            {**CONFIG, "metrology.audit_variance_runs": 1},
            "metrology.audit_variance_runs",
        ),
    ],
)
def test_unusable_setting_fails_before_anything_runs(
    audited_repo: Path,
    write_user_config: UserConfigWriter,
    config: dict[str, object],
    expected_text: str,
) -> None:
    write_user_config(config)

    with pytest.raises(BaselinePreflightError, match=expected_text):
        prepare_baseline(audited_repo, default_registry(), profile=None, model=None)


def test_missing_model_error_names_the_flag(
    audited_repo: Path, write_user_config: UserConfigWriter
) -> None:
    write_user_config({"metrology.audit_profile": "p"})

    with pytest.raises(BaselinePreflightError, match="--model"):
        prepare_baseline(audited_repo, default_registry(), profile=None, model=None)


def test_no_profile_is_an_audit_skill_error(
    audited_repo: Path, write_user_config: UserConfigWriter
) -> None:
    write_user_config({"metrology.audit_model": "m"})

    with pytest.raises(AuditSkillError, match="provider profile"):
        prepare_baseline(audited_repo, default_registry(), profile=None, model=None)


def test_project_config_in_the_measured_repo_is_honored(
    audited_repo: Path,
    write_user_config: UserConfigWriter,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    write_user_config(CONFIG)
    write_project_config(audited_repo, {"metrology.audit_model": "project-model"})
    run_test_git(audited_repo, "add", "-A")
    run_test_git(audited_repo, "commit", "-q", "-m", "project config")

    plan = prepare_baseline(audited_repo, default_registry(), profile=None, model=None)

    assert plan.model == "project-model"


def test_no_remote_and_no_recorded_id_fails_with_the_identity_error(
    repo_no_remote: Path, write_user_config: UserConfigWriter
) -> None:
    write_user_config(CONFIG)
    (repo_no_remote / "README.md").write_text("# x\n", encoding="utf-8")
    run_test_git(repo_no_remote, "add", "-A")
    run_test_git(repo_no_remote, "commit", "-q", "-m", "initial")

    with pytest.raises(MetrologyIdentityError):
        prepare_baseline(repo_no_remote, default_registry(), profile=None, model=None)
