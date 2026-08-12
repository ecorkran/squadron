"""Pydantic schema for events.yaml — validates raw YAML into typed
structures, then ``manifest.py`` converts to the ``Binding``/``EventManifest``
dataclasses the rest of the events package consumes (mirrors
``pipeline/schema.py``'s split between validation and the runtime shape).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from squadron.events import EventType


class BindingEntrySchema(BaseModel):
    """One `{action, params}` entry inside a `bindings:` event list."""

    model_config = ConfigDict(extra="forbid")

    action: str
    params: dict[str, object] = {}

    @field_validator("action")
    @classmethod
    def _action_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("'action' must be a non-empty string")
        return value


class EventManifestSchema(BaseModel):
    """Top-level events.yaml structure."""

    model_config = ConfigDict(extra="forbid")

    plugins: list[str] = []
    bindings: dict[str, list[BindingEntrySchema]] = {}
    disable: list[str] = []

    @field_validator("bindings")
    @classmethod
    def _validate_event_keys(
        cls, value: dict[str, list[BindingEntrySchema]]
    ) -> dict[str, list[BindingEntrySchema]]:
        valid = {member.value for member in EventType}
        for key in value:
            if key not in valid:
                raise ValueError(f"unknown event '{key}' in bindings — valid events: {sorted(valid)}")
        return value


def parse_manifest_yaml(raw: Any, *, manifest_path: str) -> EventManifestSchema:
    """Validate raw YAML (already ``yaml.safe_load``ed) against the schema.

    Raises:
        ManifestError-compatible ``ValueError``: naming *manifest_path* and
            Pydantic's own field-level detail. Callers wrap this in
            ``manifest.ManifestError`` for a consistent exception type.
    """
    try:
        return EventManifestSchema.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{manifest_path}: {exc}") from exc
