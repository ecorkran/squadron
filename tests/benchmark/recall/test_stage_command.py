"""The hidden ``_stage`` comb command (slice 430 D6, D8), with the model call stubbed."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from squadron.benchmark.recall.review_output import read_findings
from squadron.cli.commands import benchmark_recall_stage
from squadron.cli.commands.benchmark_recall import build_recall_app
from squadron.data import data_dir
from squadron.metrology.recall_run_models import CombVerdict
from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.recipes.comb_call import COMB_ALLOWED_TOOLS, render_findings
from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import TemplateOutput, load_template
from tests.benchmark.recall.committed import RESULTS_DIR
from tests.benchmark.recall.fixtures.bug_repo.build import BuiltBugRepo
from tests.benchmark.recall.support import fake_services

COMB_SCRIPT = RESULTS_DIR / "20261113-comb" / "comb.py"


def _comb_render() -> Callable[[list[dict[str, str]]], str]:
    spec = importlib.util.spec_from_file_location("hand_run_comb", COMB_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render


def test_render_matches_comb_py_on_a_real_case() -> None:
    review = json.loads((RESULTS_DIR / "20261112-grid2" / "175-haiku-xhigh-1.json").read_text())
    findings = [f for f in read_findings(review) if f.severity in {"CONCERN", "FAIL"}]
    precision = json.loads(
        (RESULTS_DIR / "20261112-grid2" / "precision" / "175-findings.json").read_text()
    )
    items = [item for item in precision if item["ref"].startswith("haiku-xhigh/1/")]
    assert len(items) == len(findings) > 0
    assert render_findings(findings) == _comb_render()(items)


def _write_input(path: Path) -> list[dict[str, Any]]:
    review = json.loads((RESULTS_DIR / "20261112-grid2" / "175-haiku-xhigh-1.json").read_text())
    findings = [f.model_dump(mode="json") for f in read_findings(review)[:2]]
    path.write_text(json.dumps(findings), encoding="utf-8")
    return findings


def _invoke(tmp_path: Path, bug_repo: BuiltBugRepo, output: Path) -> Any:
    input_path = tmp_path / "in.json"
    _write_input(input_path)
    app = build_recall_app(lambda _repo: fake_services(tmp_path))
    args = ["_stage", "--template", "comb", "--input", str(input_path), "--output", str(output)]
    args += ["--model", "sonnet", "--diff", bug_repo.base]
    return CliRunner().invoke(app, args)


def test_output_written_after_the_call(
    tmp_path: Path, bug_repo: BuiltBugRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    async def fake_call(template: Any, inputs: dict[str, str], **kwargs: Any) -> ReviewResult:
        seen.update(template=template.name, inputs=inputs, kwargs=kwargs)
        raw = "F1: KEEP — real defect\nF2: DROP — style"
        return ReviewResult(
            verdict=Verdict.UNKNOWN,
            findings=[],
            raw_output=raw,
            template_name="comb",
            input_files=inputs,
        )

    monkeypatch.setattr(benchmark_recall_stage, "run_review_with_profile", fake_call)
    monkeypatch.chdir(bug_repo.repo)
    output = tmp_path / "out.json"
    result = _invoke(tmp_path, bug_repo, output)
    assert result.exit_code == 0, result.output
    assert seen["template"] == "comb"
    assert seen["kwargs"]["allowed_tools"] == list(COMB_ALLOWED_TOOLS)
    assert seen["kwargs"]["model_allows_tools"] is True
    assert seen["inputs"]["findings"].startswith("### F1 [")
    assert seen["inputs"]["changed_files"]  # git diff base..HEAD in the sandbox
    document = json.loads(output.read_text())
    assert document["raw_output"].startswith("F1: KEEP")
    assert document["decisions"] == {
        "F1": [CombVerdict.KEEP.value, "real defect"],
        "F2": ["DROP", "style"],
    }


def test_no_output_file_when_the_call_raises(
    tmp_path: Path, bug_repo: BuiltBugRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_call(*_args: Any, **_kwargs: Any) -> ReviewResult:
        raise RuntimeError("provider down")

    monkeypatch.setattr(benchmark_recall_stage, "run_review_with_profile", failing_call)
    monkeypatch.chdir(bug_repo.repo)
    output = tmp_path / "out.json"
    result = _invoke(tmp_path, bug_repo, output)
    assert result.exit_code == 1
    assert "provider down" in result.output
    assert not output.exists()


#: Keys the shipped comb sets for itself: its own name, and no Claude Code settings (reviews
#: stopped loading them after the measured runs; the recorded file is left as it was).
_COMB_OWN_KEYS = frozenset({"name", "description", "setting_sources"})


def _measured_keys(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {key: value for key, value in loaded.items() if key not in _COMB_OWN_KEYS}


def test_comb_template_is_the_measured_truth_only_prompt_with_decisions_output() -> None:
    builtin = data_dir() / "templates" / "comb.yaml"
    # The prompt is pinned to the measured one: the truth-only comb of 2026-11-22 (#389).
    measured = RESULTS_DIR / "20261122-martian" / "comb-truth.yaml"
    assert _measured_keys(builtin) == _measured_keys(measured)
    template = load_template(builtin)
    assert template.name == "comb" and template.output is TemplateOutput.DECISIONS


def test_an_alias_with_tool_use_false_withholds_the_comb_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    no_tools: dict[str, ModelAlias] = {
        "plain": {"profile": "openrouter", "model": "v/m", "tool_use": False}
    }
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(no_tools))
    assert benchmark_recall_stage.resolve_stage_model("plain").allows_tools is False
