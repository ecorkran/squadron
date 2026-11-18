"""Import part 1: the hand-run review outputs into ``RecallRun.reviews`` (D10).

Each ``<case>-<config>-<run>.json`` directly under a grid folder becomes one review entry.
A file byte-identical to one already read is a duplicate and is listed, not imported.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from squadron.benchmark.recall.import_plan import ImportContext, ImportPlan, folder_date
from squadron.benchmark.recall.review_output import (
    ReviewOutputError,
    read_effort,
    read_findings,
    read_usage,
)
from squadron.metrology.recall_run_models import (
    IMPORT_SOURCE_PREFIX,
    UNKNOWN_MARKER,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
    Unknown,
    run_record_id,
)

#: The grid folders holding review outputs, in read order. grid1 is read last because its
#: 27 files are byte copies of grid2 files; reading grid2 first lists the copies (D10).
REVIEW_FOLDERS = ("20261112-grid2", "20261113-grid3", "20261112-grid1")
_REQUIRED = ("model", "profile", "max_output_tokens", "template_name", "squadron_version")


class HandRunNameError(ValueError):
    """A hand-run file name is not ``<case>-<config>-<run>.json``."""


def split_output_name(path: Path) -> tuple[str, str, int]:
    """``<case>-<config>-<run>.json`` to (case, config, run index)."""
    case, sep, rest = path.stem.partition("-")
    config, sep2, run = rest.rpartition("-")
    if not (sep and sep2 and case and config and run.isdigit()):
        raise HandRunNameError(f"file name {path.name!r} is not <case>-<config>-<run>.json")
    return case, config, int(run)


def plan_reviews(results_dir: Path, context: ImportContext, plan: ImportPlan) -> None:
    seen: dict[str, Path] = {}
    for folder in REVIEW_FOLDERS:
        for path in sorted((results_dir / folder).glob("*.json")):
            try:
                data = path.read_bytes()
            except OSError as exc:
                plan.skip(str(path), f"unreadable: {exc}")
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                plan.duplicates.append(f"{path} (same bytes as {seen[digest]})")
                continue
            seen[digest] = path
            _plan_one(path, folder, data, digest, context, plan)


def _plan_one(
    path: Path, folder: str, data: bytes, digest: str, context: ImportContext, plan: ImportPlan
) -> None:
    try:
        case_name, alias, run_index = split_output_name(path)
        document = _load_document(data)
        case = context.cases_by_hand_id.get(case_name)
        if case is None:
            plan.skip(str(path), f"no case record has hand_run_id {case_name!r}")
            return
        entry = _review_entry(document, alias, folder, digest, context.case_set)
    except (HandRunNameError, ReviewOutputError) as exc:
        plan.skip(str(path), str(exc))
        return
    run_id = run_record_id(case.case_id, run_index)
    run = plan.runs.setdefault(run_id, RecallRun(case_id=case.case_id, run_index=run_index))
    if entry.entry_key in run.reviews:
        other = run.reviews[entry.entry_key].alias
        plan.skip(str(path), f"same stage identity as config {other!r} in this run")
        return
    run.reviews[entry.entry_key] = entry
    plan.raw_outputs[digest] = data
    plan.count_unknowns(entry.config)


def _load_document(data: bytes) -> dict[str, Any]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewOutputError(f"not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ReviewOutputError("not a JSON object")
    fields = cast(dict[str, Any], document)
    missing = [name for name in (*_REQUIRED, "tools_given") if name not in fields]
    if missing:
        raise ReviewOutputError(f"missing field(s) {missing}")
    return fields


def _review_config(document: dict[str, Any]) -> StageConfig:
    marker = f"{UNKNOWN_MARKER}:{document['template_name']}@{document['squadron_version']}"
    return StageConfig(
        model=document["model"],
        profile=document["profile"],
        template_hash=marker,
        tool_use=_tool_use(document["tools_given"]),
        max_output_tokens=document["max_output_tokens"],
    )


def _tool_use(tools: object) -> bool | Unknown:
    """Non-empty ``tools_given`` is ``True``, empty ``False``; ``null`` (Codex outputs, whose
    own tools squadron does not list) was not recorded, so it is the unknown marker."""
    if tools is None:
        return UNKNOWN_MARKER
    if not isinstance(tools, list):
        raise ReviewOutputError("field 'tools_given' is neither a list nor null")
    return bool(cast(list[object], tools))


def _review_entry(
    document: dict[str, Any], alias: str, folder: str, digest: str, case_set: str
) -> StageEntry:
    return StageEntry(
        kind=StageKind.REVIEW,
        config=_review_config(document),
        effort_configured=read_effort(document),
        effort_sent=None,
        findings=read_findings(document),
        usage=read_usage(document),
        outcome=StageOutcome.OK,
        leak=RecallLeakVerdict.NOT_SCANNED,
        source=f"{IMPORT_SOURCE_PREFIX}{folder}",
        case_set=case_set,
        raw_ref=digest,
        alias=alias,
        created=folder_date(folder),
    )
