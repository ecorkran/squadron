"""Import part 2: the hand-run comb outputs into ``RecallRun.combs`` (D10).

``out/<comb>/<case>-<reviewer>-<run>.json`` attaches to that case run's review entry whose
alias is ``<reviewer>``. A ``+`` in the folder name is a chain: ``luna-r+opus-high`` is
opus-high run on what the ``luna-r`` folder's entry kept. Decisions are re-parsed from the
stored ``raw_output``. F-ids are positional per call, so each is mapped to its review
finding through the file's ``refs``; the ``P*`` entries (stage-one drops) are ignored.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from squadron.benchmark.recall.hand_run_reviews import HandRunNameError, split_output_name
from squadron.benchmark.recall.import_plan import ImportContext, ImportPlan, folder_date
from squadron.benchmark.recall.review_output import (
    ReviewOutputError,
    read_effort,
    read_usage,
)
from squadron.metrology.recall_run_models import (
    IMPORT_SOURCE_PREFIX,
    UNKNOWN_MARKER,
    CombDecision,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
    chain_key,
    comb_slot,
    run_record_id,
)
from squadron.recipes.comb_call import finding_id_at
from squadron.recipes.decisions import parse_decisions

COMB_FOLDER = "20261113-comb"
COMB_OUTPUTS = "out"
#: The commit holding the hand-run ``comb.yaml`` prompt the comb outputs used (D10).
COMB_TEMPLATE_COMMIT = "9bc108a6"
CHAIN_FOLDER_SEPARATOR = "+"
FINDING_REF_PREFIX = "F"
NO_DECISION_REASON = "comb output holds no parseable decision line"


def comb_template_marker(folder: str) -> str:
    """``comb.yaml@9bc108a6#<folder>``: the folder keeps combs with no other identity apart."""
    return f"comb.yaml@{COMB_TEMPLATE_COMMIT}#{folder}"


def plan_combs(results_dir: Path, context: ImportContext, plan: ImportPlan) -> None:
    root = results_dir / COMB_FOLDER / COMB_OUTPUTS
    folders = (
        sorted((p for p in root.iterdir() if p.is_dir()), key=_chain_order) if root.is_dir() else []
    )
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            try:
                _plan_one(path, folder.name, context, plan)
            except (HandRunNameError, ReviewOutputError) as exc:
                plan.skip(str(path), str(exc))


def _chain_order(folder: Path) -> tuple[int, str]:
    """Shorter chains first, so a chain's parent entry exists when it is read."""
    return folder.name.count(CHAIN_FOLDER_SEPARATOR), folder.name


def _plan_one(path: Path, folder: str, context: ImportContext, plan: ImportPlan) -> None:
    case_name, reviewer, run_index = split_output_name(path)
    data = _read_bytes(path)
    document = _load_document(data)
    case = context.cases_by_hand_id.get(case_name)
    if case is None:
        plan.skip(str(path), f"no case record has hand_run_id {case_name!r}")
        return
    run = plan.runs.get(run_record_id(case.case_id, run_index))
    review_key = None if run is None else _review_key(run, reviewer)
    if run is None or review_key is None:
        plan.skip(str(path), f"no imported review {reviewer!r} run {run_index} for case {case_name}")
        return
    stages = folder.split(CHAIN_FOLDER_SEPARATOR)
    parent = _parent_chain(run, review_key, stages[:-1])
    if parent is None:
        plan.skip(str(path), f"no imported first-stage comb {stages[:-1]} for this review")
        return
    digest = hashlib.sha256(data).hexdigest()
    entry = _comb_entry(document, run.reviews[review_key], folder, stages[-1], digest, context.case_set)
    chain = chain_key([*parent, entry.entry_key])
    run.combs[comb_slot(review_key, chain)] = entry
    plan.raw_outputs[digest] = data
    plan.count_unknowns(entry.config)


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReviewOutputError(f"unreadable: {exc}") from exc


def _load_document(data: bytes) -> dict[str, Any]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewOutputError(f"not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ReviewOutputError("not a JSON object")
    fields = cast(dict[str, Any], document)
    if not isinstance(fields.get("refs"), dict) or not isinstance(fields.get("raw_output"), str):
        raise ReviewOutputError("missing field 'refs' (object) or 'raw_output' (string)")
    if "effort" not in fields:
        raise ReviewOutputError("missing field 'effort'")
    return fields


def _review_key(run: RecallRun, alias: str) -> str | None:
    return next((key for key, entry in run.reviews.items() if entry.alias == alias), None)


def _parent_chain(run: RecallRun, review_key: str, aliases: list[str]) -> list[str] | None:
    """The comb entry keys of the stored chain whose stage aliases are *aliases*, in order."""
    chain: list[str] = []
    for alias in aliases:
        match = next(
            (
                entry.entry_key
                for slot, entry in run.combs.items()
                if entry.alias == alias
                and slot == comb_slot(review_key, chain_key([*chain, entry.entry_key]))
            ),
            None,
        )
        if match is None:
            return None
        chain.append(match)
    return chain


def _comb_entry(
    document: dict[str, Any], review: StageEntry, folder: str, alias: str, digest: str, case_set: str
) -> StageEntry:
    by_fid = _finding_ids_by_fid(document["refs"], len(review.findings))
    parsed = parse_decisions(document["raw_output"], list(by_fid))
    decisions: dict[str, CombDecision] = {
        by_fid[fid]: decision for fid, decision in parsed.decisions.items()
    }
    # No findings sent (stage one kept none) means no call was made: ok, nothing decided.
    failed = parsed.is_empty and bool(by_fid)
    return StageEntry(
        kind=StageKind.COMB,
        config=StageConfig(
            model=UNKNOWN_MARKER,
            profile=UNKNOWN_MARKER,
            template_hash=comb_template_marker(folder),
            tool_use=UNKNOWN_MARKER,
            max_output_tokens=UNKNOWN_MARKER,
        ),
        effort_configured=read_effort(document),
        effort_sent=None,
        decisions=decisions,
        usage=read_usage(document),
        outcome=StageOutcome.CONFIG_FAILURE if failed else StageOutcome.OK,
        outcome_reason=NO_DECISION_REASON if failed else None,
        leak=RecallLeakVerdict.NOT_SCANNED,
        source=f"{IMPORT_SOURCE_PREFIX}{COMB_FOLDER}",
        case_set=case_set,
        raw_ref=digest,
        alias=alias,
        created=folder_date(COMB_FOLDER),
        duplicate_decisions=parsed.duplicate_decisions,
        unknown_ids=parsed.unknown_ids,
    )


def _finding_ids_by_fid(refs: dict[str, Any], finding_count: int) -> dict[str, str]:
    """``F<n>`` to the review's finding id, through ``<reviewer>/<run>/<index>`` refs."""
    mapped: dict[str, str] = {}
    for fid, ref in refs.items():
        if not fid.startswith(FINDING_REF_PREFIX):
            continue
        index_text = str(ref).rsplit("/", 1)[-1]
        if not index_text.isdigit() or int(index_text) >= finding_count:
            raise ReviewOutputError(f"ref {fid} -> {ref!r} names no finding of the review")
        mapped[fid.upper()] = finding_id_at(int(index_text))
    return mapped
