"""Builders and fakes for recipe review tests (slice 434). No model is called."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from squadron.core.models import Effort
from squadron.core.usage import CostBasis, RunTelemetry, TokenUsage
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.recall_run_models import RecallFinding, content_key
from squadron.providers.errors import ProviderError
from squadron.recipes.comb_call import call_comb
from squadron.recipes.recipe import Recipe
from squadron.recipes.recipe_outcome import RecipeOutcome, RecipeProgress
from squadron.recipes.recipe_runner import RecipeReviewCall, run_recipe
from squadron.recipes.stage_config import builtin_template, plan_recipe
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.templates import ReviewTemplate

#: The two-reviewer, two-comb recipe used across the tests.
RECIPE_NAME = "duo"
REVIEWERS = ("rev-a", "rev-b")
COMBS = ("comb-1", "comb-2")
RECIPE_TEXT = f"name: {RECIPE_NAME}\nreviewers: [{', '.join(REVIEWERS)}]\ncombs: [{', '.join(COMBS)}]\n"


def recall_finding(index: int, severity: str = "CONCERN") -> RecallFinding:
    title = f"finding {index}"
    location = f"src/app.py:{index}"
    return RecallFinding(
        finding_id=f"F{index}",
        content_key=content_key(location, title, f"text {index}"),
        severity=severity,
        category=None,
        location=location,
        title=title,
        description=f"text {index}",
    )


def review_finding(title: str, severity: Severity = Severity.CONCERN) -> ReviewFinding:
    return ReviewFinding(
        severity=severity, title=title, description=f"{title} detail", location="src/app.py:3"
    )


def review_result(
    findings: Sequence[ReviewFinding],
    verdict: Verdict = Verdict.CONCERNS,
    *,
    cost: float | None = 0.01,
    raw: str = "raw review",
    effort: Effort | None = None,
) -> ReviewResult:
    result = ReviewResult(
        verdict=verdict,
        findings=list(findings),
        raw_output=raw,
        template_name="code",
        input_files={},
        model="vendor/x",
        cost_usd=cost,
        duration_seconds=2.0,
        turns=1,
        tool_calls_made=3,
        effort=effort,
    )
    return result


def decisions_text(*pairs: tuple[str, str]) -> str:
    """Comb output in the ``F<n>: KEEP|DROP — reason`` format ``parse_decisions`` reads."""
    return "\n".join(f"{fid}: {word} — because" for fid, word in pairs)


Scripted = ReviewResult | BaseException


@dataclass
class CallRecord:
    alias: str
    template: str
    allowed_tools: list[str] | None
    cwd: str | None
    inputs: dict[str, str]


@dataclass
class ScriptedReviewCall:
    """Matches ``run_review_with_profile``'s use: returns or raises per (alias, call index)."""

    script: dict[str, list[Scripted]]
    calls: list[CallRecord] = field(default_factory=list[CallRecord])
    delay_s: float = 0.0

    async def __call__(
        self, template: ReviewTemplate, inputs: dict[str, str], **kwargs: Any
    ) -> ReviewResult:
        import asyncio

        alias = str(kwargs["alias"])
        self.calls.append(
            CallRecord(
                alias, template.name, kwargs.get("allowed_tools"), inputs.get("cwd"), dict(inputs)
            )
        )
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        index = sum(1 for c in self.calls if c.alias == alias) - 1
        outcomes = self.script[alias]
        outcome = outcomes[min(index, len(outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def aliases(self) -> list[str]:
        return [c.alias for c in self.calls]


def provider_error(text: str = "rate limited") -> ProviderError:
    """A failure that reported nothing it spent."""
    return ProviderError(text)


def provider_error_with_spend(
    text: str = "timed out", *, cost: float | None = 0.03, prompt_tokens: int = 500
) -> ProviderError:
    """A failure carrying what the call spent before it failed, as review_client sets it."""
    error = ProviderError(
        text,
        telemetry=RunTelemetry(turns=2, usage=TokenUsage(prompt=prompt_tokens)),
        duration_seconds=4.0,
    )
    error.cost_usd = cost
    error.cost_basis = CostBasis.PROVIDER if cost is not None else None
    return error


@dataclass
class FakeRecipeSink:
    """Collects ``write(record, raw_outputs)``; ``fail_with`` raises instead."""

    writes: list[tuple[Any, dict[str, str]]] = field(default_factory=list[tuple[Any, dict[str, str]]])
    fail_with: type[BaseException] | None = None

    def write(self, record: Any, raw_outputs: dict[str, str]) -> None:
        if self.fail_with is MetrologyStoreError:
            raise MetrologyStoreError("store unwritable")
        if self.fail_with is not None:
            raise self.fail_with("disk full")
        self.writes.append((record, raw_outputs))


def defect_repo(root: Path) -> Path:
    """A git repo with a base commit and one commit adding a defect."""
    root.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    (root / "src" / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    git("commit", "-qam", "add defect")
    return root


def run_scripted(
    recipe: Recipe,
    scripted: ScriptedReviewCall,
    cwd: Path,
    *,
    changed: Sequence[str] = ("src/app.py",),
    progress: RecipeProgress | None = None,
) -> RecipeOutcome:
    """Run *recipe* on the ``code`` template with scripted model answers."""
    call = RecipeReviewCall(
        template=builtin_template("code"),
        inputs={"cwd": str(cwd), "diff": "HEAD~1"},
        options={},
        review_call=scripted,
        comb_call=call_comb,
    )
    return asyncio.run(
        run_recipe(
            recipe,
            call=call,
            plan=plan_recipe(recipe, call.template),
            changed_files=changed,
            cwd=cwd,
            slow_after_s=60,
            progress=progress if progress is not None else RecipeProgress(),
        )
    )
