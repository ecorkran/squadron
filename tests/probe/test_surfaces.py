import json
import logging
from pathlib import Path
from typing import Any

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
        self,
        home: Path,
        project: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        commands_root = _machine_root(CommandTarget.CLAUDE, home)
        _install_claude_skill(commands_root, POST_366_DISPATCHER)
        dispatcher_file = commands_root / surfaces.CLAUDE_DISPATCHER_FILE
        read_text = Path.read_text

        def read_text_or_fail(path: Path, *args: Any, **kwargs: Any) -> str:
            # File permissions are no stand-in: they do nothing as root or on Windows.
            if path == dispatcher_file:
                raise PermissionError("simulated unreadable file")
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text_or_fail)

        assert CLAUDE.analysis_skill_installed(project) is None
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


FIXTURES = Path(__file__).parent / "fixtures"
PLUGINS_FILE = Path(".claude/plugins/installed_plugins.json")


def _write_plugins(home: Path, content: str) -> None:
    plugins_file = home / PLUGINS_FILE
    plugins_file.parent.mkdir(parents=True, exist_ok=True)
    plugins_file.write_text(content)


def _plugin_registry(key: str, scope: str, project_path: Path | None = None) -> str:
    entry: dict[str, str] = {"scope": scope}
    if project_path is not None:
        entry["projectPath"] = str(project_path)
    return json.dumps({"version": 2, "plugins": {key: [entry]}})


class TestClaudePluginDetection:
    def test_real_format_fixture_is_true(self, home: Path, project: Path) -> None:
        _write_plugins(home, (FIXTURES / "installed_plugins.json").read_text())

        assert CLAUDE.understand_plugin_installed(project) is True

    def test_file_absent_is_false(self, home: Path, project: Path) -> None:
        assert CLAUDE.understand_plugin_installed(project) is False

    def test_project_scope_for_this_project_is_true(self, home: Path, project: Path) -> None:
        _write_plugins(home, _plugin_registry("understand-anything@market", "project", project))

        assert CLAUDE.understand_plugin_installed(project) is True

    def test_project_scope_for_another_path_is_false(
        self, home: Path, project: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "elsewhere"
        _write_plugins(home, _plugin_registry("understand-anything@market", "project", other))

        assert CLAUDE.understand_plugin_installed(project) is False

    def test_other_plugins_only_is_false(self, home: Path, project: Path) -> None:
        _write_plugins(home, _plugin_registry("something-else@market", "user"))

        assert CLAUDE.understand_plugin_installed(project) is False

    @pytest.mark.parametrize(
        "content",
        [
            "not json",
            json.dumps({"version": 2}),
            json.dumps({"plugins": {"understand-anything@market": {"scope": "user"}}}),
            json.dumps({"plugins": {"understand-anything@market": ["not an entry"]}}),
        ],
        ids=["not-json", "plugins-missing", "plugins-value-not-a-list", "entry-not-an-object"],
    )
    def test_unexpected_shape_is_unknown(
        self, home: Path, project: Path, content: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        _write_plugins(home, content)

        assert CLAUDE.understand_plugin_installed(project) is None
        assert _warnings(caplog)


class TestCodexPluginDetection:
    def test_skill_present_is_true(self, home: Path, project: Path) -> None:
        skill_file = _machine_root(CommandTarget.AGENTS, home) / surfaces.CODEX_PLUGIN_SKILL_FILE
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("# understand")

        assert CODEX.understand_plugin_installed(project) is True

    def test_skill_absent_is_false(self, home: Path, project: Path) -> None:
        assert CODEX.understand_plugin_installed(project) is False
