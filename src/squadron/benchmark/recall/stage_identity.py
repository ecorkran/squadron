"""Live stage identity from the alias registry (slice 430 D4, D9).

``live_stage_config`` is what ``run`` keys pending calls by (with ``entry_key``) and what a
live entry is stored with. ``LiveStageResolver`` gives ``report`` the identity a recipe
alias resolves to now: its ``config_key`` and the effort its profile actually sends. A
reviewer's recipe options (no tools, a rules file) are part of both, as in production.
"""

from __future__ import annotations

import logging

from squadron.benchmark.auth_check import UnresolvedProfileError, resolve_alias_profile
from squadron.benchmark.recall.scoring_select import StageIdentity
from squadron.core.models import Effort
from squadron.metrology.recall_run_models import StageConfig, StageKind
from squadron.models.aliases import get_all_aliases, model_effort
from squadron.pipeline.usage_capture import effort_sent_by_profile
from squadron.recipes.recipe import ReviewerOptions
from squadron.recipes.stage_config import (
    COMB_TEMPLATE_NAME,
    StageConfigError,
    builtin_template_hash,
    stage_config,
)

_logger = logging.getLogger(__name__)

#: The built-in template each stage kind sends.
STAGE_TEMPLATES: dict[StageKind, str] = {StageKind.REVIEW: "code", StageKind.COMB: COMB_TEMPLATE_NAME}


class StageIdentityError(ValueError):
    """An alias or template that gives no live stage identity."""


def live_stage_config(
    alias: str, stage_kind: StageKind, options: ReviewerOptions | None = None
) -> tuple[StageConfig, Effort | None]:
    """The stage config and configured effort of *alias* called with *options*.

    An unknown alias or template raises.
    """
    if alias not in get_all_aliases():
        raise StageIdentityError(f"model alias {alias!r} is not in the alias registry")
    try:
        model, profile = resolve_alias_profile(alias)
        template_hash = builtin_template_hash(STAGE_TEMPLATES[stage_kind])
    except (UnresolvedProfileError, StageConfigError) as exc:
        raise StageIdentityError(str(exc)) from exc
    return stage_config(alias, model, profile.value, template_hash, options), model_effort(alias)


class LiveStageResolver:
    """``StageIdentityResolver`` over the live alias registry.

    An alias the registry does not know has no live identity: it returns ``None`` (so only
    imported entries can match it) and logs a WARNING naming the alias once.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, StageKind, ReviewerOptions | None], StageIdentity | None] = {}

    def resolve(
        self, alias: str, stage_kind: StageKind, options: ReviewerOptions | None = None
    ) -> StageIdentity | None:
        key = (alias, stage_kind, options)
        if key not in self._cache:
            self._cache[key] = self._resolve(alias, stage_kind, options)
        return self._cache[key]

    @staticmethod
    def _resolve(
        alias: str, stage_kind: StageKind, options: ReviewerOptions | None
    ) -> StageIdentity | None:
        try:
            config, effort = live_stage_config(alias, stage_kind, options)
        except StageIdentityError as exc:
            _logger.warning("recall report: no live identity for %s: %s", alias, exc)
            return None
        sent = effort_sent_by_profile(str(config.profile), effort)
        return StageIdentity(config.config_key, sent)
