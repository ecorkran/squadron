import logging
from pathlib import Path

import pytest

from squadron.probe import surfaces
from squadron.probe.surfaces import SURFACES
from squadron.skills.targets import DELIVERIES, CommandTarget

CLAUDE = SURFACES[CommandTarget.CLAUDE]
CODEX = SURFACES[CommandTarget.AGENTS]

POST_366_DISPATCHER = "Valid skills: `tech-debt-audit`, `understand`\n"
PRE_366_DISPATCHER = "Valid skills: `tech-debt-audit`\n"


@pytest.fixture
def home() -> Path:
    """The per-test HOME that tests/conftest.py points the process at."""
    return Path("~").expanduser()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    return project_dir


def _machine_root(target: CommandTarget, home: Path) -> Path:
    return home / DELIVERIES[target].machine_root


def _project_root(target: CommandTarget, project: Path) -> Path:
    return project / DELIVERIES[target].local_root


def _install_claude_skill(commands_root: Path, dispatcher: str | None) -> None:
    skill_file = commands_root / surfaces.CLAUDE_SKILL_FILE
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("# understand")
    if dispatcher is not None:
        dispatcher_file = commands_root / surfaces.CLAUDE_DISPATCHER_FILE
        dispatcher_file.parent.mkdir(parents=True)
        dispatcher_file.write_text(dispatcher)


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno == logging.WARNING]


class TestClaudeSkillDetection:
    def test_nothing_installed_is_false(self, home: Path, project: Path) -> None:
        assert CLAUDE.analysis_skill_installed(project) is False

    def test_machine_scope_install_is_true(self, home: Path, project: Path) -> None:
        _install_claude_skill(_machine_root(CommandTarget.CLAUDE, home), POST_366_DISPATCHER)

        assert CLAUDE.analysis_skill_installed(project) is True

    def test_project_scope_install_is_true(self, home: Path, project: Path) -> None:
        _install_claude_skill(_project_root(CommandTarget.CLAUDE, project), POST_366_DISPATCHER)

        assert CLAUDE.analysis_skill_installed(project) is True

    def test_pre_366_dispatcher_is_false(self, home: Path, project: Path) -> None:
        _install_claude_skill(_machine_root(CommandTarget.CLAUDE, home), PRE_366_DISPATCHER)

        assert CLAUDE.analysis_skill_installed(project) is False

    def test_dispatcher_without_valid_skills_line_is_unknown(
        self, home: Path, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _install_claude_skill(_machine_root(CommandTarget.CLAUDE, home), "no list here\n")

        assert CLAUDE.analysis_skill_installed(project) is None
        assert _warnings(caplog)

    def test_unreadable_dispatcher_is_unknown(
        self, home: Path, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        commands_root = _machine_root(CommandTarget.CLAUDE, home)
        _install_claude_skill(commands_root, POST_366_DISPATCHER)
        dispatcher_file = commands_root / surfaces.CLAUDE_DISPATCHER_FILE
        dispatcher_file.chmod(0o000)
        try:
            assert CLAUDE.analysis_skill_installed(project) is None
        finally:
            dispatcher_file.chmod(0o644)
        assert _warnings(caplog)

    def test_skill_without_dispatcher_is_false(self, home: Path, project: Path) -> None:
        _install_claude_skill(_machine_root(CommandTarget.CLAUDE, home), None)

        assert CLAUDE.analysis_skill_installed(project) is False


class TestCodexSkillDetection:
    def _install(self, skills_root: Path) -> None:
        skill_file = skills_root / surfaces.CODEX_SKILL_FILE
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("# understand")

    def test_absent_is_false(self, home: Path, project: Path) -> None:
        assert CODEX.analysis_skill_installed(project) is False

    def test_machine_scope_is_true(self, home: Path, project: Path) -> None:
        self._install(_machine_root(CommandTarget.AGENTS, home))

        assert CODEX.analysis_skill_installed(project) is True

    def test_project_scope_is_true(self, home: Path, project: Path) -> None:
        self._install(_project_root(CommandTarget.AGENTS, project))

        assert CODEX.analysis_skill_installed(project) is True


def test_every_target_has_a_surface_with_contract_keys() -> None:
    assert set(SURFACES) == set(CommandTarget)
    assert {spec.key for spec in SURFACES.values()} == {"claude-code", "codex"}
