"""One review-profile cascade shared by ``sq review`` and pipeline review steps.

Cascade: explicit → alias profile → ``template.profile`` →
``default_review_profile`` config → ``ProfileName.SDK``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from squadron.config.manager import get_config
from squadron.providers.base import ProfileName

if TYPE_CHECKING:
    from squadron.review.templates import ReviewTemplate


class ReviewProfileSource(StrEnum):
    """Which cascade channel supplied the review profile."""

    EXPLICIT = "explicit"
    ALIAS = "alias"
    TEMPLATE = "template"
    CONFIG = "config"
    DEFAULT = "default"


@dataclass(frozen=True)
class ReviewProfileChoice:
    """A resolved review profile and the channel it came from."""

    name: str
    source: ReviewProfileSource


def _config_profile() -> str | None:
    """Return ``default_review_profile`` when configured as a string, else None."""
    value = get_config("default_review_profile")
    return value if isinstance(value, str) else None


def resolve_review_profile(
    explicit: str | None,
    alias_profile: str | None,
    template: ReviewTemplate | None,
) -> ReviewProfileChoice:
    """Resolve the review profile through the shared cascade."""
    if explicit is not None:
        return ReviewProfileChoice(explicit, ReviewProfileSource.EXPLICIT)
    if alias_profile is not None:
        return ReviewProfileChoice(alias_profile, ReviewProfileSource.ALIAS)
    if template is not None and template.profile is not None:
        return ReviewProfileChoice(template.profile, ReviewProfileSource.TEMPLATE)
    config_profile = _config_profile()
    if config_profile is not None:
        return ReviewProfileChoice(config_profile, ReviewProfileSource.CONFIG)
    return ReviewProfileChoice(ProfileName.SDK.value, ReviewProfileSource.DEFAULT)


def review_profile_source(explicit_present: bool, template: ReviewTemplate | None) -> bool:
    """True when the caller named a profile that justifies a literal model id.

    Counts an explicit profile, ``template.profile`` and ``default_review_profile``.
    Never counts the alias profile (the alias already matched) or the sdk default
    (that fallback is what silently rescued typo'd aliases, issue #67).
    """
    return (
        explicit_present
        or (template is not None and template.profile is not None)
        or _config_profile() is not None
    )
