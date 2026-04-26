"""Declarative template-input registry for pipeline review actions.

Each template declares which ``inputs`` keys it populates and how to derive them
from a ``SliceInfo``.  Adding a new template requires only a new entry in
``TEMPLATE_INPUTS``; the dispatch logic in ``_resolve_slice_inputs`` becomes a
single call to ``resolve_template_inputs``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from squadron.review.git_utils import resolve_slice_diff_range
from squadron.review.persistence import SliceInfo


@dataclass(frozen=True)
class TemplateInputSpec:
    """Specification for one key in the ``inputs`` dict a template requires."""

    key: str
    source: Callable[[SliceInfo, str], str | None]


def _design_file(info: SliceInfo, _cwd: str) -> str | None:
    return info["design_file"] if info["design_file"] else None


def _arch_file(info: SliceInfo, _cwd: str) -> str | None:
    return info["arch_file"]


def _tasks_input(info: SliceInfo, _cwd: str) -> str | None:
    if not info["task_files"]:
        return None
    return f"project-documents/user/tasks/{info['task_files'][0]}"


def _diff_range(info: SliceInfo, cwd: str) -> str | None:
    return resolve_slice_diff_range(info["index"], cwd)


TEMPLATE_INPUTS: dict[str, list[TemplateInputSpec]] = {
    "slice": [
        TemplateInputSpec(key="input", source=_design_file),
        TemplateInputSpec(key="against", source=_arch_file),
    ],
    "tasks": [
        TemplateInputSpec(key="input", source=_tasks_input),
        TemplateInputSpec(key="against", source=_design_file),
    ],
    "arch": [
        TemplateInputSpec(key="input", source=_arch_file),
    ],
    "code": [
        TemplateInputSpec(key="diff", source=_diff_range),
    ],
}


def resolve_template_inputs(
    template_name: str,
    info: SliceInfo,
    cwd: str,
    inputs: dict[str, str],
) -> None:
    """Populate ``inputs`` from the registry entry for ``template_name``.

    Iterates each ``TemplateInputSpec`` for the template.  When ``source``
    returns a non-None value, ``inputs[spec.key]`` is set.  Unknown template
    names produce no changes and no error.
    """
    for spec in TEMPLATE_INPUTS.get(template_name, []):
        value = spec.source(info, cwd)
        if value is not None:
            inputs[spec.key] = value
