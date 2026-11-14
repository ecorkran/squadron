"""Production wiring of the leak-rule inputs (slice 424 Task 32).

Every ``LeakRules`` field is populated from a real fact; an input that cannot be read
refuses naming it, and nothing falls back to a default.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.leak_paths import path_hits
from squadron.benchmark.leak_rule_source import (
    PYPROJECT,
    LeakRuleSource,
    distribution_name,
    installed_package_location,
    uv_cache_dir,
)
from squadron.benchmark.transcripts import ToolCall
from squadron.core.process_runner import ProcessResult
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed, ok
from tests.benchmark.test_fix_case_runner import fix_case

PYPROJECT_TEXT = '[project]\nname = "Widget_Pkg"\nversion = "1"\n'


class FakeHost:
    def serves_host(self, host: str) -> bool:
        return host == "github.com"


def handler(pyproject: ProcessResult | str = PYPROJECT_TEXT, remote_url: str = "") -> Any:
    url = remote_url or "https://github.com/acme/widgets.git"

    def handle(call: RunnerCall) -> ProcessResult:
        argv = call.argv
        if argv[:2] == ("git", "show") and argv[-1].endswith(f":{PYPROJECT}"):
            return pyproject if isinstance(pyproject, ProcessResult) else ok(argv, pyproject)
        if argv[:3] == ("git", "show", "-s"):
            return ok(argv, "2026-11-01T10:00:00+00:00\n")
        if argv == ("git", "remote"):
            return ok(argv, "origin\n")
        if argv[:3] == ("git", "remote", "get-url"):
            return ok(argv, url + "\n")
        if argv == ("uv", "cache", "dir"):
            return ok(argv, "/cache/uv\n")
        return failed(argv, stderr=f"unexpected {argv}")

    return handle


def source(runner: ScriptedRunner, tmp_path: Path) -> LeakRuleSource:
    return LeakRuleSource(
        runner=runner,
        repo_root=tmp_path / "checkout",
        host=FakeHost(),  # type: ignore[arg-type]
        real_home=tmp_path / "home",
        install_location=installed_package_location(),
        uv_cache=Path("/cache/uv"),
        timeout_s=5,
    )


def sandbox(tmp_path: Path) -> Any:
    return SimpleNamespace(
        tree=tmp_path / "sbx", home=tmp_path / "sbx.home", output_dir=tmp_path / "sbx.out"
    )


def test_every_leak_rules_field_is_populated(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler())
    rules = source(runner, tmp_path).rules_for(sandbox(tmp_path), fix_case())
    assert rules.tree == tmp_path / "sbx"
    assert rules.tree_roots and rules.sandbox_roots and rules.protected_roots
    assert rules.real_home == tmp_path / "home"
    assert rules.distribution_name == "widget-pkg"
    assert (rules.host_owner, rules.host_repo) == ("acme", "widgets")
    assert installed_package_location() in rules.protected_roots
    assert Path("/cache/uv") in rules.protected_roots
    assert tmp_path / "checkout" in rules.protected_roots


def test_the_installed_package_is_protected_but_a_sibling_library_is_not(tmp_path: Path) -> None:
    location = installed_package_location()
    assert location.name == "squadron" and (location / "__init__.py").is_file()
    rules = source(ScriptedRunner(handler()), tmp_path).rules_for(sandbox(tmp_path), fix_case())

    own_file = ToolCall("Read", {"file_path": str(location / "__init__.py")})
    sibling = ToolCall("Read", {"file_path": str(location.parent / "pydantic" / "main.py")})
    assert path_hits(own_file, rules)
    assert path_hits(sibling, rules) == []


def test_per_case_facts_are_read_once(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler())
    rules = source(runner, tmp_path)
    case = fix_case()
    rules.rules_for(sandbox(tmp_path), case)
    calls = len(runner.calls)
    rules.rules_for(sandbox(tmp_path), case)
    assert len(runner.calls) == calls


def test_unreadable_pyproject_refuses_naming_the_file(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler(pyproject=failed(("git", "show"), 128, "fatal: no such path")))
    with pytest.raises(BenchmarkRefusal, match=PYPROJECT):
        source(runner, tmp_path).rules_for(sandbox(tmp_path), fix_case())


@pytest.mark.parametrize(
    ("text", "message"),
    [("not = [toml", "not valid TOML"), ("[tool.x]\na = 1\n", r"no \[project\]\.name")],
)
def test_a_pyproject_without_a_name_refuses_naming_it(text: str, message: str) -> None:
    runner = ScriptedRunner(handler(pyproject=text))
    with pytest.raises(BenchmarkRefusal, match=message):
        distribution_name(runner, Path("/r"), "a" * 40, 5)


def test_a_case_with_no_code_host_remote_refuses(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler(remote_url="https://gitlab.example/acme/widgets.git"))
    with pytest.raises(BenchmarkRefusal, match="no code host repository"):
        source(runner, tmp_path).rules_for(sandbox(tmp_path), fix_case())


def test_a_case_without_a_readable_issue_ref_refuses(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler())
    with pytest.raises(BenchmarkRefusal, match="issue ref"):
        source(runner, tmp_path).rules_for(sandbox(tmp_path), fix_case(source_ref="nonsense"))


def test_uv_cache_dir_failure_refuses() -> None:
    runner = ScriptedRunner(lambda call: failed(call.argv, 2, "uv broke"))
    with pytest.raises(BenchmarkRefusal, match="uv broke"):
        uv_cache_dir(runner)
