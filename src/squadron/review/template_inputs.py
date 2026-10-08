"""Declarative template-input registry for pipeline review actions.

Each template declares which ``inputs`` keys it populates and how to derive them
from a ``SliceInfo``.  Adding a new template requires only a new entry in
``TEMPLATE_INPUTS``; the dispatch logic in ``_resolve_slice_inputs`` becomes a
single call to ``resolve_template_input_parts``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from squadron.review.git_utils import resolve_slice_diff_range
from squadron.review.parts import review_stems
from squadron.review.persistence import TASKS_DIR, SliceInfo, slice_review_stem

#: Review input keys whose values are document paths that must exist on disk
#: for the review to be grounded. Other keys (diff refs, file globs, cwd)
#: have their own resolution logic and are not plain file paths.
FILE_INPUT_KEYS = ("input", "against")


@dataclass(frozen=True)
class TemplateInputSpec:
    """Specification for one key in the ``inputs`` dict a template requires.

    ``source`` returns every value it has for the key: empty when it has
    nothing, one element for a scalar input. ``fans_out`` marks the key whose
    values each get their own review part (a split task breakdown); a spec
    without it uses only the first value.
    """

    key: str
    source: Callable[[SliceInfo, str], list[str]]
    fans_out: bool = False


def _design_file(info: SliceInfo, _cwd: str) -> list[str]:
    return [info["design_file"]] if info["design_file"] else []


def _arch_file(info: SliceInfo, _cwd: str) -> list[str]:
    return [info["arch_file"]] if info["arch_file"] else []


def _task_files(info: SliceInfo, _cwd: str) -> list[str]:
    return [str(TASKS_DIR / name) for name in info["task_files"]]


def _diff_range(info: SliceInfo, cwd: str) -> list[str]:
    # Never empty: an unresolvable range raises DiffRangeUnresolvedError.
    return [resolve_slice_diff_range(info["index"], cwd)]


TEMPLATE_INPUTS: dict[str, list[TemplateInputSpec]] = {
    "slice": [
        TemplateInputSpec(key="input", source=_design_file),
        TemplateInputSpec(key="against", source=_arch_file),
    ],
    "tasks": [
        TemplateInputSpec(key="input", source=_task_files, fans_out=True),
        TemplateInputSpec(key="against", source=_design_file),
    ],
    "arch": [
        TemplateInputSpec(key="input", source=_arch_file),
    ],
    "code": [
        TemplateInputSpec(key="diff", source=_diff_range),
    ],
    "judge.tasks-vs-slice": [
        TemplateInputSpec(key="input", source=_task_files, fans_out=True),
        TemplateInputSpec(key="against", source=_design_file),
    ],
    "judge.slice-vs-arch": [
        TemplateInputSpec(key="input", source=_design_file),
        TemplateInputSpec(key="against", source=_arch_file),
    ],
}


def missing_input_files(inputs: dict[str, str]) -> list[tuple[str, str]]:
    """Return (key, path) pairs for ``FILE_INPUT_KEYS`` that name no real file.

    A path counts as present when it resolves relative to the process cwd
    (how content injection reads it) or relative to ``inputs["cwd"]`` (how
    SDK review agents read it). Callers treat a non-empty result as a hard
    error: a review whose input document is silently absent from the prompt
    produces a fabricated verdict instead of a failure (issue #18).
    """
    cwd = Path(inputs.get("cwd", "."))
    missing: list[tuple[str, str]] = []
    for key in FILE_INPUT_KEYS:
        value = inputs.get(key)
        if value is None:
            continue
        if Path(value).is_file() or (cwd / value).is_file():
            continue
        missing.append((key, value))
    return missing


def review_artifact_stems(template_name: str, info: SliceInfo, cwd: str) -> list[str]:
    """The artifact stem of every part a slice-derived review of ``template_name`` saves.

    One stem, or ``.part-1`` .. ``.part-N`` when the template's fan-out input has
    two or more values — exactly the files ``resolve_template_input_parts`` makes
    the review write.
    """
    stem = slice_review_stem(info["index"], template_name, info["slice_name"])
    fan_out = next((spec for spec in TEMPLATE_INPUTS.get(template_name, []) if spec.fans_out), None)
    values = fan_out.source(info, cwd) if fan_out is not None else []
    return review_stems(stem, values) if values else [stem]


def resolve_template_input_parts(
    template_name: str,
    info: SliceInfo,
    cwd: str,
    inputs: dict[str, str],
) -> list[dict[str, str]]:
    """Resolve ``inputs`` for ``template_name`` into one dict per review part.

    Scalar keys are copied into every dict; the one ``fans_out`` key gets one
    value per dict. ``inputs`` is not mutated. Unknown template names yield a
    single unchanged copy.

    A key already present in ``inputs`` was supplied explicitly by the caller
    and wins over the slice-derived value, and is not fanned out: an explicit
    ``input:`` means one part. This mirrors the CLI, where an explicit
    ``--diff`` takes precedence over ``resolve_slice_diff_range``:
    ``sq review code 118 --diff main`` and a pipeline step carrying both
    ``slice`` and ``diff`` must mean the same thing.

    A fan-out source with no values yields one dict without that key, so the
    caller's missing-required-input check reports it.

    Raises:
        ValueError: If more than one spec in the entry sets ``fans_out``.
    """
    specs = TEMPLATE_INPUTS.get(template_name, [])
    if sum(spec.fans_out for spec in specs) > 1:
        raise ValueError(f"template '{template_name}' declares more than one fan-out input")

    base = dict(inputs)
    fan_key: str | None = None
    fan_values: list[str] = []
    for spec in specs:
        if spec.key in inputs:
            continue
        values = spec.source(info, cwd)
        if spec.fans_out:
            fan_key, fan_values = spec.key, values
        elif values:
            base[spec.key] = values[0]

    if fan_key is None or not fan_values:
        return [base]
    return [{**base, fan_key: value} for value in fan_values]
