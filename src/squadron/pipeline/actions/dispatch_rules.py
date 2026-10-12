"""Pipeline glue for project rule selection (slice 935).

Translates pipeline concepts (``StepTypeName``, ``ProviderType``, the rules
directory resolution) into a :class:`RuleContext`. Everything pipeline-specific
about project rules lives here so ``dispatch.py`` doesn't grow and
``squadron.project_rules`` never imports from the pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from pathlib import Path

from squadron.config.manager import get_config
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.project_rules.conventions import ConventionsSource
from squadron.project_rules.frontmatter import RuleStep
from squadron.project_rules.render import render_project_rules
from squadron.project_rules.selection import (
    MAX_CHARS_KEY,
    ProjectRules,
    RuleContext,
    select_project_rules,
)
from squadron.providers.base import ProviderType
from squadron.review.git_utils import GIT_COMMAND_TIMEOUT_SECONDS, run_git
from squadron.review.rules import resolve_rules_dir

_logger = logging.getLogger(__name__)

#: Dispatching step types and the rule step kind each selects for (D3).
_RULE_STEPS: dict[StepTypeName, RuleStep] = {
    StepTypeName.DESIGN: RuleStep.DESIGN,
    StepTypeName.TASKS: RuleStep.TASKS,
    StepTypeName.IMPLEMENT: RuleStep.IMPLEMENT,
    StepTypeName.DISPATCH: RuleStep.DISPATCH,
}

#: The conventions file each provider type loads on its own (D5).
_NATIVE_CONVENTIONS: dict[ProviderType, ConventionsSource | None] = {
    ProviderType.SDK: ConventionsSource.CLAUDE_MD,
    ProviderType.OPENAI_OAUTH: ConventionsSource.AGENTS_MD,
    ProviderType.OPENAI: None,
}

#: Step kinds whose ``paths`` rules are matched against the project's tracked files.
_FILE_SCOPED_STEPS = frozenset({RuleStep.IMPLEMENT})


class ProjectRulesContextError(RuntimeError):
    """The pipeline couldn't build a rule context (unmapped type, git failure)."""


def rule_step_for(step_type: StepTypeName) -> RuleStep:
    try:
        return _RULE_STEPS[step_type]
    except KeyError:
        raise ProjectRulesContextError(
            f"No project-rules step kind for step type {step_type.value!r}"
        ) from None


def native_conventions_for(provider: ProviderType) -> ConventionsSource | None:
    try:
        return _NATIVE_CONVENTIONS[provider]
    except KeyError:
        raise ProjectRulesContextError(
            f"No native-conventions entry for provider type {provider.value!r}"
        ) from None


def tracked_files(cwd: str) -> list[str]:
    """``git ls-files`` under ``cwd``. Any git failure raises; it never means "no files"."""
    result = run_git(["ls-files"], cwd=cwd)
    if result is None:
        raise ProjectRulesContextError(
            f"git ls-files could not run in {cwd} (git missing, bad directory, or "
            f"no answer within {GIT_COMMAND_TIMEOUT_SECONDS}s)"
        )
    if result.returncode != 0:
        raise ProjectRulesContextError(
            f"git ls-files failed in {cwd} (exit {result.returncode}): {result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def rule_step_from_params(params: Mapping[str, object]) -> StepTypeName:
    """The dispatching step's kind: the phase step's param, else a bare ``dispatch``."""
    return StepTypeName(str(params.get(RULES_STEP_PARAM, StepTypeName.DISPATCH)))


def sdk_native_record() -> dict[str, object]:
    """The record for an SDK dispatch, which loads the project's files itself (D4)."""
    return {"conventions": ConventionsSource.SDK_NATIVE.value}


def _select(step_type: StepTypeName, provider: ProviderType, cwd: str) -> ProjectRules:
    return select_project_rules(build_rule_context(step_type, provider, cwd))


async def project_rules_for_dispatch(
    step_type: StepTypeName, provider: ProviderType, cwd: str
) -> tuple[str, dict[str, object]]:
    """The ``## Project Rules`` block to append to a dispatch's instructions, and its record.

    SDK providers get no block and the ``sdk-native`` record. Selection does git
    and file I/O, so it runs off the event loop; rendering is pure.
    """
    if provider == ProviderType.SDK:
        return "", sdk_native_record()
    rules = await asyncio.to_thread(_select, step_type, provider, cwd)
    if rules.conventions is None and not rules.rules:
        _logger.warning(
            "Step kind %s dispatches with no project rules: no conventions file and no "
            "selected rule files under %s",
            step_type.value,
            cwd,
        )
    return render_project_rules(rules), rules.to_record()


def build_rule_context(step_type: StepTypeName, provider: ProviderType, cwd: str) -> RuleContext:
    """The :class:`RuleContext` for one dispatch of ``step_type`` through ``provider``."""
    step_kind = rule_step_for(step_type)
    native = native_conventions_for(provider)
    rules_dir, _source = resolve_rules_dir(cwd, None, None)
    max_chars = get_config(MAX_CHARS_KEY, cwd=cwd)
    if not isinstance(max_chars, int):
        raise TypeError(f"{MAX_CHARS_KEY} config value is not an int: {max_chars!r}")
    return RuleContext(
        step_kind=step_kind,
        file_paths=tracked_files(cwd) if step_kind in _FILE_SCOPED_STEPS else None,
        root=Path(cwd),
        rules_dir=rules_dir,
        native=native,
        max_chars=max_chars,
    )
