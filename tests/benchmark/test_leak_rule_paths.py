"""Leak path rule: collection from tool inputs and the hit test (slice 424 Task 19)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.leak_paths import path_hits
from squadron.benchmark.leak_scan import LEAK_RULES_VERSION, LeakRules, build_leak_rules
from squadron.benchmark.leak_shell import command_tokens
from squadron.benchmark.transcripts import ToolCall


class Layout:
    """A user's home holding the checkout and the benchmark root, plus outside directories."""

    def __init__(self, base: Path) -> None:
        self.real_home = base / "user"
        self.bench = self.real_home / ".local" / "share" / "bench"
        self.tree = self.bench / "s1"
        self.sandbox_home = self.bench / "s1.home"
        self.output = self.bench / "s1.out"
        self.repo_root = self.real_home / "src" / "checkout"
        self.install = base / "site" / "squadron-install"
        self.uv_cache = base / "uvcache"
        self.unrelated = base / "unrelated"
        for directory in (self.tree, self.sandbox_home, self.output, self.repo_root):
            directory.mkdir(parents=True)

    def rules(self) -> LeakRules:
        return build_leak_rules(
            tree=self.tree,
            home=self.sandbox_home,
            output_dir=self.output,
            real_home=self.real_home,
            repo_root=self.repo_root,
            install_location=self.install,
            uv_cache=self.uv_cache,
            distribution_name="squadron-ai",
            host_owner="owner",
            host_repo="repo",
        )


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path)


def bash(command: str) -> ToolCall:
    return ToolCall(tool="Bash", input={"command": command})


def read(path: str) -> ToolCall:
    return ToolCall(tool="Read", input={"file_path": path})


class TestHits:
    @pytest.mark.parametrize(
        ("name", "build"),
        [
            ("read_in_checkout", lambda x: read(f"{x.repo_root}/src/x.py")),
            ("read_home_dotfile_tilde", lambda x: read("~/.ssh/config")),
            ("bash_tilde", lambda x: bash("cat ~/.ssh/config")),
            ("bash_home_itself", lambda x: bash("ls ~")),
            ("dotdot_escape", lambda x: bash("cd .. && cat ../../other/file")),
            ("uv_cache", lambda x: read(f"{x.uv_cache}/wheels/x.whl")),
            ("install_location", lambda x: bash(f"cat {x.install}/squadron/cli.py")),
            ("other_sandbox", lambda x: bash(f"ls {x.bench}/s2")),
            ("sandbox_parent", lambda x: bash(f"ls {x.bench}")),
            (
                "unbalanced_quotes",
                lambda x: bash(f'echo "unterminated; cat {x.repo_root}/secret'),
            ),
            ("operator_attached", lambda x: bash(f"ls;cat {x.repo_root}/x")),
            ("option_value", lambda x: bash(f"tool --file={x.repo_root}/x")),
            ("key_value_path", lambda x: bash(f"dd if={x.repo_root}/x of=/dev/null")),
            ("key_value_tilde", lambda x: bash("dd if=~/.ssh/id_rsa of=/dev/null")),
            ("nested_command", lambda x: bash(f'bash -c "cat {x.repo_root}/x"')),
            ("glob_pattern", lambda x: ToolCall("Glob", {"pattern": f"{x.repo_root}/**/*.py"})),
            ("grep_path", lambda x: ToolCall("Grep", {"pattern": "needle", "path": str(x.repo_root)})),
            (
                "notebook",
                lambda x: ToolCall("NotebookEdit", {"notebook_path": f"{x.repo_root}/n.ipynb"}),
            ),
            ("absolute_with_dotdot", lambda x: read(f"{x.tree}/../../../../src/checkout/x.py")),
        ],
    )
    def test_path_is_a_hit(self, layout: Layout, name: str, build: object) -> None:
        call = build(layout)  # type: ignore[operator]
        assert path_hits(call, layout.rules()), name

    @pytest.mark.parametrize(
        ("name", "build"),
        [
            ("venv_in_tree", lambda x: read(f"{x.tree}/.venv/lib/python3.12/site.py")),
            ("tree_file", lambda x: read(f"{x.tree}/src/a.py")),
            ("sandbox_home", lambda x: bash(f"cat {x.sandbox_home}/.gitconfig")),
            ("sandbox_output", lambda x: bash(f"cat {x.output}/issue.md")),
            ("dotdot_stays_inside", lambda x: bash("cat ./a/../b")),
            ("relative_path", lambda x: bash("cat src/a.py")),
            ("unrelated_outside_home", lambda x: bash(f"cat {x.unrelated}/f")),
            ("system_path", lambda x: bash("cat /etc/hostname && ls /usr/bin")),
            ("url_token", lambda x: bash("curl https://example.com/a/b")),
            ("pattern_on_non_glob_tool", lambda x: ToolCall("Read", {"pattern": f"{x.repo_root}/x"})),
            ("relative_glob_pattern", lambda x: ToolCall("Glob", {"pattern": "**/*.py"})),
            ("non_string_fields", lambda x: ToolCall("Read", {"file_path": 3, "command": ["ls"]})),
            ("empty_command", lambda x: bash("")),
        ],
    )
    def test_path_is_not_a_hit(self, layout: Layout, name: str, build: object) -> None:
        call = build(layout)  # type: ignore[operator]
        assert path_hits(call, layout.rules()) == [], name

    def test_hit_names_the_normalized_offending_path(self, layout: Layout) -> None:
        hits = path_hits(bash(f"cat {layout.repo_root}/a/../b.py"), layout.rules())
        assert hits == [f"{layout.repo_root}/b.py"]

    def test_symlink_in_tree_does_not_count_as_leaving_it(self, layout: Layout) -> None:
        (layout.tree / ".venv").symlink_to(layout.unrelated, target_is_directory=True)
        layout.unrelated.mkdir()
        assert path_hits(bash(f"{layout.tree}/.venv/bin/python"), layout.rules()) == []


class TestTokens:
    def test_operators_are_split_from_words(self) -> None:
        assert command_tokens("a;b && c|d") == ["a", ";", "b", "&&", "c", "|", "d"]

    def test_unbalanced_quotes_fall_back_to_word_tokens(self) -> None:
        assert "/x/y" in command_tokens('echo "oops /x/y')

    def test_unbalanced_quote_fallback_keeps_the_separators(self) -> None:
        assert command_tokens('ls; gh issue view "3') == ["ls", ";", "gh", "issue", "view", "3"]

    def test_rules_version_is_an_int(self) -> None:
        assert isinstance(LEAK_RULES_VERSION, int)
