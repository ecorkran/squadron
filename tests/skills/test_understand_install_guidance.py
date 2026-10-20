"""Every place that tells a user how to get a graph carries the install commands."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

CLAUDE_MARKETPLACE_COMMAND = "/plugin marketplace add Egonex-AI/Understand-Anything"
CLAUDE_INSTALL_COMMAND = "/plugin install understand-anything"
CODEX_INSTALL_COMMAND = (
    "curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything"
    "/main/install.sh | bash -s codex"
)
INSTALL_COMMANDS = [
    CLAUDE_MARKETPLACE_COMMAND,
    CLAUDE_INSTALL_COMMAND,
    CODEX_INSTALL_COMMAND,
]

GUIDANCE_FILES = [
    REPO_ROOT / "commands" / "analysis" / "understand.md",
    REPO_ROOT / "commands" / "analysis" / "agents" / "analysis-understand" / "SKILL.md",
]


@pytest.mark.parametrize("guidance_file", GUIDANCE_FILES, ids=lambda path: path.name)
@pytest.mark.parametrize("command", INSTALL_COMMANDS)
def test_install_command_appears_verbatim(guidance_file: Path, command: str) -> None:
    lines = guidance_file.read_text(encoding="utf-8").splitlines()

    assert any(f"`{command}`" in line for line in lines), (
        f"{guidance_file} is missing `{command}` on a single line"
    )
