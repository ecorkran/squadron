from pathlib import Path

import pytest

from squadron.skills.manifest import (
    SHIPPED_DEFAULT_ORIGIN,
    SkillsManifest,
    load,
    load_effective,
    merge,
)
from squadron.skills.models import PackEntry

VALID_TOML = """
[packs.analysis]
source = "bundled"
prefix = "analysis"

[packs.myskill]
source = "./local/path"
dispatch_file = "myskill"
"""

MALFORMED_TOML = "packs = { broken = [ }]"


class TestLoad:
    def test_valid_toml_returns_manifest(self, tmp_path: Path) -> None:
        p = tmp_path / "skills.toml"
        p.write_text(VALID_TOML)
        manifest = load(p)
        assert "analysis" in manifest.packs
        assert "myskill" in manifest.packs
        assert manifest.packs["analysis"].prefix == "analysis"
        assert manifest.packs["myskill"].dispatch_file == "myskill"
        assert manifest.origin == str(p)

    def test_malformed_toml_raises_value_error_with_path(self, tmp_path: Path) -> None:
        p = tmp_path / "skills.toml"
        p.write_text(MALFORMED_TOML)
        with pytest.raises(ValueError, match=str(p)):
            load(p)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            load(p)


class TestMerge:
    def _manifest(self, packs: dict, origin: str) -> SkillsManifest:
        return SkillsManifest(packs={k: PackEntry(**v) for k, v in packs.items()}, origin=origin)

    def test_additive_union(self) -> None:
        user = self._manifest(
            {"pack_a": {"source": "bundled", "prefix": "a"}},
            "user",
        )
        project = self._manifest(
            {"pack_b": {"source": "bundled", "prefix": "b"}},
            "project",
        )
        result = merge(user, project)
        assert "pack_a" in result.packs
        assert "pack_b" in result.packs
        assert result.origin == "merged"

    def test_project_wins_on_collision(self) -> None:
        user = self._manifest(
            {"shared": {"source": "bundled", "prefix": "user-version"}},
            "user",
        )
        project = self._manifest(
            {"shared": {"source": "bundled", "prefix": "project-version"}},
            "project",
        )
        result = merge(user, project)
        assert result.packs["shared"].prefix == "project-version"


class TestLoadEffective:
    def test_no_files_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Patch out both user manifest and shipped default so we can assert the None path.
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", tmp_path / "no-such.toml")
        monkeypatch.setattr("squadron.skills.manifest._load_shipped_default", lambda: None)
        result = load_effective(cwd=tmp_path)
        assert result is None

    def test_only_user_level_returns_user_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_file = tmp_path / "skills.toml"
        user_file.write_text(VALID_TOML)
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", user_file)
        monkeypatch.setattr("squadron.skills.manifest._load_shipped_default", lambda: None)
        result = load_effective(cwd=tmp_path)
        assert result is not None
        assert result.origin == str(user_file)

    def test_both_files_returns_merged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        user_file = tmp_path / "skills-user.toml"
        user_file.write_text('[packs.user_pack]\nsource = "bundled"\nprefix = "user"\n')
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", user_file)
        monkeypatch.setattr("squadron.skills.manifest._load_shipped_default", lambda: None)

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        squadron_dir = project_dir / ".squadron"
        squadron_dir.mkdir()
        (squadron_dir / "skills.toml").write_text(
            '[packs.proj_pack]\nsource = "bundled"\nprefix = "proj"\n'
        )

        result = load_effective(cwd=project_dir)
        assert result is not None
        assert result.origin == "merged"
        assert "user_pack" in result.packs
        assert "proj_pack" in result.packs


class TestLoadEffectiveWithDefault:
    def test_shipped_default_present_with_no_user_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # With no user or project manifest, load_effective() returns the analysis pack
        # from the shipped default.
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", tmp_path / "no-such.toml")
        result = load_effective(cwd=tmp_path)
        assert result is not None
        assert "analysis" in result.packs
        assert result.origin == SHIPPED_DEFAULT_ORIGIN

    def test_user_manifest_overrides_shipped_default_pack(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # User manifest with a different analysis entry wins; other shipped packs survive.
        user_file = tmp_path / "skills.toml"
        user_file.write_text('[packs.analysis]\nsource = "bundled"\nprefix = "custom-analysis"\n')
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", user_file)

        result = load_effective(cwd=tmp_path)
        assert result is not None
        assert result.packs["analysis"].prefix == "custom-analysis"
        assert result.origin == "merged"

    def test_merged_origin_when_user_manifest_alongside_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_file = tmp_path / "skills.toml"
        user_file.write_text('[packs.extra]\nsource = "bundled"\nprefix = "extra"\n')
        monkeypatch.setattr("squadron.skills.manifest.USER_MANIFEST", user_file)

        result = load_effective(cwd=tmp_path)
        assert result is not None
        assert result.origin == "merged"
        assert "analysis" in result.packs
        assert "extra" in result.packs
