"""Leak git, code-host and own-package rules (slice 424 Task 20)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from squadron.benchmark.leak_git_package import git_host_hits, own_package_hits
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.benchmark.transcripts import ToolCall

OWNER = "acme-org"
REPOSITORY = "widget"
REPOSITORY_URL = f"https://github.com/{OWNER}/{REPOSITORY}"
REPOSITORY_SCP = f"git@github.com:{OWNER}/{REPOSITORY}.git"
DISTRIBUTION = "widget-ai"


@pytest.fixture
def rules(tmp_path: Path) -> LeakRules:
    for name in ("tree", "home", "out", "user", "checkout"):
        (tmp_path / name).mkdir()
    return build_leak_rules(
        tree=tmp_path / "tree",
        home=tmp_path / "home",
        output_dir=tmp_path / "out",
        real_home=tmp_path / "user",
        repo_root=tmp_path / "checkout",
        install_location=tmp_path / "site",
        uv_cache=tmp_path / "uvcache",
        distribution_name=DISTRIBUTION,
        host_owner=OWNER,
        host_repo=REPOSITORY,
    )


def bash(command: str) -> ToolCall:
    return ToolCall(tool="Bash", input={"command": command})


GIT_HOST_HITS = [
    "gh issue view 3",
    "/usr/local/bin/gh pr list",
    # A gh command that reads from a repository on the host.
    "gh repo view",
    "gh repo view --json nameWithOwner,description",
    "gh repo clone a/b",
    "gh auth status && gh pr list",
    "command -v gh && gh issue view 3",
    "env GH_HOST=x gh api /repos",
    "FOO=1 gh issue view 3",
    "ls && gh issue view 3",
    "git status\ngh issue view 3",
    "git -C /elsewhere log",
    "git -C .. log",
    "git --git-dir=/x log",
    "git --git-dir /x log",
    "git --work-tree=/elsewhere status",
    "git -c core.pager=cat -C /elsewhere log",
    # git told to read from the case's repository.
    f"git clone {REPOSITORY_URL}",
    f"git clone --depth 1 {REPOSITORY_URL}.git /tmp/x",
    f"git clone {REPOSITORY_SCP}",
    f"git fetch {REPOSITORY_URL} main",
    f"git pull {REPOSITORY_SCP}",
    f"git ls-remote {REPOSITORY_URL}",
    f"git remote add up {REPOSITORY_URL}",
    f"git remote -v add up {REPOSITORY_URL}",
    f"git remote set-url origin {REPOSITORY_SCP}",
    f"git config remote.origin.url {REPOSITORY_URL}",
    f"git submodule add {REPOSITORY_URL}",
    f"curl https://github.com/{OWNER}/{REPOSITORY}/issues/3",
    f"curl -s https://api.github.com/repos/{OWNER}/{REPOSITORY}/issues/3",
    f"wget https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/main/x.py",
    f"curl -L https://github.com/{OWNER.upper()}/{REPOSITORY}.git",
    f"curl github.com/{OWNER}/{REPOSITORY}",
    'bash -c "gh issue view 3"',
    "timeout 30 gh issue view 3",
    "env -i gh issue view 3",
    "nice -n 5 gh pr list",
    "time -p gh pr list",
    "echo 3 | xargs gh issue view",
    'eval "gh issue view 3"',
    "echo `gh issue view 3`",
    'echo "`gh issue view 3`"',
    "echo $(gh issue view 3)",
    # F001: git aimed outside the tree through its environment variables.
    "GIT_DIR=/elsewhere git log",
    "GIT_WORK_TREE=/elsewhere git status",
    "FOO=1 GIT_DIR=/elsewhere git log",
    "env GIT_DIR=/elsewhere git log",
    # F002: unbalanced quoting must not hide a later command, and a wrapper option's
    # separate value is not the program.
    'ls; gh issue view "3',
    "echo hi && gh issue view '3",
    "sudo -u bob gh issue view 3",
    "sudo -g wheel -u bob gh pr list",
    "env -u HOME gh issue view 3",
    "timeout -s KILL 30 gh pr list",
    "nice -n 5 gh pr list",
    "stdbuf -o L gh pr list",
]
GIT_HOST_NON_HITS = [
    "git status",
    "git diff",
    "git log --oneline",
    "git -C ./sub log",
    "git -C sub status",
    "git --git-dir=.git log",
    "git remote -v",
    "git remote show origin",
    # The sandbox repository has no remote, so these reach nothing unless one that names
    # the case's repository was added, and adding it is the hit.
    "git fetch",
    "git fetch origin",
    "git pull",
    # Another repository does not hold the case's answer.
    "git clone https://example.com/a/b",
    "git remote add up https://example.com/a/b",
    f"git clone https://github.com/{OWNER}/other-repo",
    # gh commands that read nothing from a repository.
    "gh",
    "gh --version",
    "gh auth status 2>&1",
    "gh help issue",
    "gh repo view --json nameWithOwner 2>&1",
    "gh repo view --json=nameWithOwner,url",
    # A lookup of where a program is runs nothing.
    "command -v gh",
    "command -v gh >/dev/null 2>&1",
    "command -V git",
    "git commit -m fetch",
    "echo gh issue view 3",
    "echo git clone x",
    "ls gh",
    "curl https://github.com/other-org/other/issues/3",
    f"curl https://github.com/{OWNER}/other-repo/issues/3",
    f"curl https://github.com/other/{REPOSITORY}",
    "curl https://example.com/index.html",
    "echo timeout 30 gh",
    "timeout 30 ls",
    "echo `date`",
    "",
    "GIT_DIR=.git git log",
    "FOO=/elsewhere git status",
    "sudo -u bob ls",
    "env -u HOME ls",
]


class TestGitAndHost:
    @pytest.mark.parametrize("command", GIT_HOST_HITS)
    def test_command_is_a_hit(self, rules: LeakRules, command: str) -> None:
        assert git_host_hits(bash(command), rules), command

    @pytest.mark.parametrize("command", GIT_HOST_NON_HITS)
    def test_command_is_not_a_hit(self, rules: LeakRules, command: str) -> None:
        assert git_host_hits(bash(command), rules) == [], command

    def test_fetch_tool_url_field_naming_the_repository_is_a_hit(self, rules: LeakRules) -> None:
        call = ToolCall("WebFetch", {"url": f"https://github.com/{OWNER}/{REPOSITORY}/issues/3"})
        assert git_host_hits(call, rules)

    def test_fetch_tool_url_field_for_another_repository_is_not(self, rules: LeakRules) -> None:
        call = ToolCall("WebFetch", {"url": "https://github.com/other/repo"})
        assert git_host_hits(call, rules) == []

    def test_git_dir_inside_the_tree_by_absolute_path_is_not_a_hit(
        self, rules: LeakRules, tmp_path: Path
    ) -> None:
        assert git_host_hits(bash(f"git -C {tmp_path}/tree/sub log"), rules) == []

    def test_hit_text_names_the_offending_invocation(self, rules: LeakRules) -> None:
        assert git_host_hits(bash(f"git clone {REPOSITORY_URL}"), rules) == [
            f"git clone {REPOSITORY_URL}"
        ]
        assert git_host_hits(bash("gh issue view 3"), rules) == ["gh issue view 3"]


PACKAGE_HITS = [
    f"uvx {DISTRIBUTION}",
    f"uvx {DISTRIBUTION.replace('-', '_')}",
    f"uvx {DISTRIBUTION}@latest",
    f"uvx --from {DISTRIBUTION} sq --help",
    f"pip install {DISTRIBUTION}==1.0",
    f"pip install -U {DISTRIBUTION}",
    f"pip3 install {DISTRIBUTION.upper()}>=1.0",
    f"python -m pip install {DISTRIBUTION}[extra]",
    f"python3.12 -m pip install {DISTRIBUTION}",
    f"uv pip install {DISTRIBUTION}",
    f"uv add {DISTRIBUTION}",
    f"uv tool install {DISTRIBUTION}",
    f"uv tool run {DISTRIBUTION}",
    f"pipx run {DISTRIBUTION}",
    f"pipx install {DISTRIBUTION}",
    f"cd x && pip install requests {DISTRIBUTION}",
    f"sudo pip install {DISTRIBUTION}",
]
PACKAGE_NON_HITS = [
    "pip install requests",
    "uvx ruff",
    "uv add pytest",
    "uv pip install -r requirements.txt",
    "uv run pytest",
    "uv sync",
    f"pip list {DISTRIBUTION}",
    f"pip uninstall {DISTRIBUTION}",
    f"echo {DISTRIBUTION}",
    f"echo pip install {DISTRIBUTION}",
    f"cat {DISTRIBUTION}.txt",
    f"pip install {DISTRIBUTION}-extras",
    f"git commit -m 'uvx {DISTRIBUTION}'",
    "",
]


class TestOwnPackage:
    @pytest.mark.parametrize("command", PACKAGE_HITS)
    def test_command_is_a_hit(self, rules: LeakRules, command: str) -> None:
        assert own_package_hits(bash(command), rules), command

    @pytest.mark.parametrize("command", PACKAGE_NON_HITS)
    def test_command_is_not_a_hit(self, rules: LeakRules, command: str) -> None:
        assert own_package_hits(bash(command), rules) == [], command

    def test_call_without_a_command_field_is_not_a_hit(self, rules: LeakRules) -> None:
        assert own_package_hits(ToolCall("Read", {"file_path": DISTRIBUTION}), rules) == []


def test_git_aimed_at_a_directory_confinement_denies_is_not_a_hit(rules: LeakRules) -> None:
    confined = replace(rules, confined_roots=(rules.real_home,))
    call = bash(f"git -C {rules.real_home}/other log")

    assert git_host_hits(call, rules) == [f"git {rules.real_home}/other"]
    assert git_host_hits(call, confined) == []
