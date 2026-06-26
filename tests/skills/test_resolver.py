from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.skills.models import PackEntry, SkillSourceError
from squadron.skills.resolver import resolve_source


class TestAbsolutePath:
    def test_valid_directory_resolves(self, tmp_path: Path) -> None:
        src = tmp_path / "mypack"
        src.mkdir()
        (src / "skill.md").write_text("# skill")

        entry = PackEntry(source=str(src), prefix="mypack")
        result = resolve_source(entry, "mypack")
        assert result == src

    def test_missing_path_raises_skill_source_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        entry = PackEntry(source=str(missing), prefix="mypack")
        with pytest.raises(SkillSourceError, match="does not exist"):
            resolve_source(entry, "mypack")

    def test_file_instead_of_dir_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "notadir.md"
        f.write_text("content")
        entry = PackEntry(source=str(f), prefix="mypack")
        with pytest.raises(SkillSourceError):
            resolve_source(entry, "mypack")


class TestUnknownSource:
    def test_unknown_format_raises_with_pack_name(self) -> None:
        entry = PackEntry(source="s3://bucket/path", prefix="mything")
        with pytest.raises(SkillSourceError, match="mything"):
            resolve_source(entry, "mything")

    def test_unknown_format_message_contains_source(self) -> None:
        entry = PackEntry(source="s3://bucket/path", prefix="mything")
        with pytest.raises(SkillSourceError, match="s3://bucket/path"):
            resolve_source(entry, "mything")


class TestGithubNoGit:
    def test_missing_git_raises_with_install_hint(self) -> None:
        entry = PackEntry(source="github:org/repo", prefix="therepo")
        with patch("squadron.skills.resolver.shutil.which", return_value=None):
            with pytest.raises(SkillSourceError, match="git"):
                resolve_source(entry, "therepo")


@pytest.mark.network
class TestGithubClone:
    def test_clone_succeeds(self, tmp_path: Path) -> None:
        # This test requires network access and a real git binary.
        entry = PackEntry(source="github:anthropics/anthropic-cookbook", prefix="cookbook")
        path = resolve_source(entry, "cookbook")
        assert path.is_dir()
        import shutil

        shutil.rmtree(str(path), ignore_errors=True)
