"""One comb call, as the hidden ``_stage`` command runs it (slice 430 D6).

The input file is a JSON list of ``RecallFinding`` (the parent stage's kept findings). They
are rendered ``F1..Fn`` by position, in the hand-run ``comb.py render`` format, and sent
with the template through ``run_review_with_profile``. The output file is written only
after the model call returns, so its absence means the call never finished (D8).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from squadron.benchmark.recall.decisions import parse_decisions
from squadron.benchmark.recall.review_output import finding_id_at
from squadron.core.models import Effort
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.recall_run_models import RecallFinding
from squadron.review.models import ReviewResult
from squadron.review.templates import ReviewTemplate

#: The comb's tools: squadron's builtins, which refuse paths outside the working directory.
COMB_ALLOWED_TOOLS = ("read_file", "list_files", "grep")
_FINDINGS = TypeAdapter(list[RecallFinding])

ReviewCall = Callable[..., Awaitable[ReviewResult]]


class StageInputError(ValueError):
    """The input file is unreadable or not a JSON list of findings."""


@dataclass(frozen=True)
class StageModel:
    """The resolved alias: what the comb call is sent with."""

    alias: str
    model: str
    profile: str
    effort: Effort | None
    max_output_tokens: int | None
    #: The alias's ``tool_use``: ``False`` withholds the comb's tools, as for ``sq review``.
    allows_tools: bool


def read_stage_input(path: Path) -> list[RecallFinding]:
    try:
        return _FINDINGS.validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise StageInputError(f"comb input {path} unreadable: {exc}") from exc


def render_findings(findings: list[RecallFinding]) -> str:
    """``### F<n> [<severity>] <title>`` blocks, F1 first: the ``comb.py render`` format."""
    blocks = [
        f"### {finding_id_at(i)} [{f.severity}] {f.title}\nLocation: {f.location}\n\n{f.description}"
        for i, f in enumerate(findings)
    ]
    return "\n\n".join(blocks)


def changed_files(runner: ProcessRunner, cwd: Path, base: str, timeout: float) -> str:
    """``git diff --name-only <base> HEAD`` in the sandbox; a failure raises."""
    result = runner.run(["git", "diff", "--name-only", base, "HEAD"], cwd=str(cwd), timeout=timeout)
    if result.returncode != 0:
        raise StageInputError(
            f"git diff --name-only {base} HEAD failed: {result.stderr.strip()[-300:]}"
        )
    return result.stdout.strip()


async def run_comb_stage(
    *,
    template: ReviewTemplate,
    findings: list[RecallFinding],
    changed: str,
    cwd: Path,
    model: StageModel,
    review_call: ReviewCall,
) -> dict[str, Any]:
    """Call the model; the output document (raw text, decisions, usage) once it returns."""
    inputs = {"findings": render_findings(findings), "changed_files": changed, "cwd": str(cwd)}
    result = await review_call(
        template,
        inputs,
        profile=model.profile,
        model=model.model,
        allowed_tools=list(COMB_ALLOWED_TOOLS),
        model_allows_tools=model.allows_tools,
        effort=model.effort,
        alias=model.alias,
        max_output_tokens=model.max_output_tokens,
    )
    ids = [finding_id_at(index) for index in range(len(findings))]
    parsed = parse_decisions(result.raw_output, ids)
    return {
        **result.to_dict(),
        "raw_output": result.raw_output,
        "decisions": {fid: [d.verdict.value, d.reason] for fid, d in parsed.decisions.items()},
    }


def write_stage_output(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
