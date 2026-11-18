"""Text for ``sq benchmark recall`` listings (slice 430)."""

from __future__ import annotations

from pathlib import Path

from squadron.metrology.recall_case_models import RealBugCase, RecallCaseSet


def render_cases(sets: list[RecallCaseSet], cases: list[RealBugCase]) -> str:
    lines = ["Case sets:"]
    lines += [f"  {s.name} v{s.version}: {len(s.case_ids)} cases" for s in sets] or ["  (none)"]
    bug_total = sum(len(case.bugs) for case in cases)
    lines.append(f"Cases: {len(cases)}, bugs: {bug_total}")
    for case in cases:
        lines.extend(_case_lines(case))
    return "\n".join(lines)


def _case_lines(case: RealBugCase) -> list[str]:
    repo = Path(case.repo).expanduser()
    status = "present" if repo.is_dir() else f"MISSING ({repo})"
    lines = [
        f"  {case.name} [{case.case_id}] kind={case.kind.value} status={case.status.value} "
        f"bugs={len(case.bugs)} repo={status}"
    ]
    for bug in case.bugs:
        extras = set(bug.extra_locations)
        derived = [loc.file for loc in bug.locations if loc not in extras]
        lines.append(f"    {bug.id} ({bug.original_review.value}): {', '.join(derived) or '-'}")
        lines += [f"      extra: {loc.file} ({loc.reason})" for loc in bug.extra_locations]
    return lines
