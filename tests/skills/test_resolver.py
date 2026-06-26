from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.skills.models import PackEntry, SkillSourceError
from squadron.skills.resolver import clone_github, resolve_source


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

    def test_github_source_via_resolve_raises(self) -> None:
        # resolve_source does not handle github: — use clone_github() instead
        entry = PackEntry(source="github:org/repo", prefix="therepo")
        with pytest.raises(SkillSourceError, match="clone_github"):
            resolve_source(entry, "therepo")


class TestGithubNoGit:
    def test_missing_git_raises_with_install_hint(self) -> None:
        with patch("squadron.skills.resolver.shutil.which", return_value=None):
            with pytest.raises(SkillSourceError, match="git"):
                clone_github("github:org/repo", "therepo")

    def test_cleanup_on_clone_failure(self) -> None:
        # When clone fails, no temp directory should be left behind
        with patch("squadron.skills.resolver.shutil.which", return_value="/usr/bin/git"):
            with patch("squadron.skills.resolver.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 128
                mock_run.return_value.stderr = b"fatal: repository not found"
                with pytest.raises(SkillSourceError, match="Failed to clone"):
                    clone_github("github:org/repo", "therepo")


@pytest.mark.network
class TestGithubClone:
    def test_clone_succeeds_and_cleans_up(self) -> None:
        # Requires network access and a real git binary.
        tmp = clone_github("github:anthropics/anthropic-cookbook", "cookbook")
        cloned_path = Path(tmp.name)
        assert cloned_path.is_dir()
        assert any(cloned_path.iterdir()), "Clone should contain at least one file"
        tmp.cleanup()
        assert not cloned_path.exists(), "TemporaryDirectory.cleanup() should remove the clone"
