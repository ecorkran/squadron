"""Live stage identity from the alias registry (slice 430 D4, D9).

``live_stage_config`` is what ``run`` keys pending calls by (with ``entry_key``) and what a
live entry is stored with. ``LiveStageResolver`` gives ``report`` the identity a recipe
alias resolves to now: its ``config_key`` and the effort its profile actually sends.
"""

from __future__ import annotations

import logging

from squadron.benchmark.auth_check import UnresolvedProfileError, resolve_alias_profile
from squadron.benchmark.recall.scoring_select import StageIdentity
from squadron.core.models import Effort
from squadron.data import data_dir
from squadron.metrology.identity import template_behavior_hash
from squadron.metrology.recall_run_models import StageConfig, StageKind
from squadron.models.aliases import (
    get_all_aliases,
    model_allows_tools,
    model_effort,
    model_max_output_tokens,
)
from squadron.pipeline.usage_capture import effort_sent_by_profile
from squadron.review.templates import load_template

_logger = logging.getLogger(__name__)

#: The built-in template each stage kind sends.
STAGE_TEMPLATES: dict[StageKind, str] = {StageKind.REVIEW: "code", StageKind.COMB: "comb"}


class StageIdentityError(ValueError):
    """An alias or template that gives no live stage identity."""


def builtin_template_hash(name: str) -> str:
    """The hash of the shipped template file. Stage calls run in a scrubbed home with no
    user templates, so the built-in is what they execute, whatever this process's home holds."""
    path = data_dir() / "templates" / f"{name}.yaml"
    if not path.is_file():
        raise StageIdentityError(f"built-in template {name!r} not found at {path}")
    return template_behavior_hash(load_template(path))


def live_stage_config(alias: str, stage_kind: StageKind) -> tuple[StageConfig, Effort | None]:
    """The stage config and configured effort of *alias*; unknown alias or template raises."""
    if alias not in get_all_aliases():
        raise StageIdentityError(f"model alias {alias!r} is not in the alias registry")
    try:
        model, profile = resolve_alias_profile(alias)
    except UnresolvedProfileError as exc:
        raise StageIdentityError(str(exc)) from exc
    template_hash = builtin_template_hash(STAGE_TEMPLATES[stage_kind])
    config = StageConfig(
        model=model,
        profile=profile.value,
        template_hash=template_hash,
        tool_use=model_allows_tools(alias),
        max_output_tokens=model_max_output_tokens(alias),
    )
    return config, model_effort(alias)


class LiveStageResolver:
    """``StageIdentityResolver`` over the live alias registry.

    An alias the registry does not know has no live identity: it returns ``None`` (so only
    imported entries can match it) and logs a WARNING naming the alias once.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, StageKind], StageIdentity | None] = {}

    def resolve(self, alias: str, stage_kind: StageKind) -> StageIdentity | None:
        key = (alias, stage_kind)
        if key not in self._cache:
            self._cache[key] = self._resolve(alias, stage_kind)
        return self._cache[key]

    @staticmethod
    def _resolve(alias: str, stage_kind: StageKind) -> StageIdentity | None:
        try:
            config, effort = live_stage_config(alias, stage_kind)
        except StageIdentityError as exc:
            _logger.warning("recall report: no live identity for %s: %s", alias, exc)
            return None
        sent = effort_sent_by_profile(str(config.profile), effort)
        return StageIdentity(config.config_key, sent)
