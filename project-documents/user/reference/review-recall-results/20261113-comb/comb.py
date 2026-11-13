"""Comb grid 2 reviews with one comb model and score the result against the precision grades.

Usage: comb.py run <comb-alias> [--runs 1] [--jobs 3]   # comb every (case, reviewer, run)
       comb.py score                                     # table over every comb in out/

Each comb call sees one review's CONCERN/FAIL findings, as a comb pass would in use.
Worktrees at each case's head must exist at $COMB_WT/<case> (see README.md).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRID = HERE.parent / "20261112-grid2"
REPOS = Path.home() / "source/repos/manta"
REVIEWERS = ("haiku-xhigh", "sol", "sonnet-high", "sonnet")
DECISION = re.compile(r"\b(F\d+)\b\W{0,6}(KEEP|DROP)\b\W*(.*)", re.IGNORECASE)


def load_cases() -> dict[str, tuple[str, str, str]]:
    rows = (line.split() for line in (GRID / "cases.txt").read_text().splitlines() if line.strip())
    return {case: (repo, base, head) for case, repo, base, head in rows}


def load_grades() -> dict[tuple[str, str], str]:
    grades: dict[tuple[str, str], str] = {}
    for path in (GRID / "precision").glob("*-graded.json"):
        data = json.loads(path.read_text())
        for issue in data["issues"]:
            for ref in issue["members"]:
                grades[(data["case"], ref)] = issue["grade"]
    return grades


def review_findings(case: str, reviewer: str, run: str) -> list[dict[str, str]]:
    items = json.loads((GRID / "precision" / f"{case}-findings.json").read_text())
    return [x for x in items if x["ref"].startswith(f"{reviewer}/{run}/")]


def render(findings: list[dict[str, str]]) -> str:
    blocks = []
    for n, x in enumerate(findings, 1):
        blocks.append(
            f"### F{n} [{x['severity']}] {x['title']}\n"
            f"Location: {x['location']}\n\n{x['description']}"
        )
    return "\n\n".join(blocks)


def changed_files(repo: str, base: str, head: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPOS / repo), "diff", "--name-only", base, head],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


async def comb_one(
    alias: str, case: str, reviewer: str, run: str, sem: asyncio.Semaphore, prefilter: str | None
) -> None:
    from squadron.models.aliases import model_effort, resolve_model_alias
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import load_template

    label = f"{prefilter}+{alias}" if prefilter else alias
    target = HERE / "out" / label / f"{case}-{reviewer}-{run}.json"
    findings = review_findings(case, reviewer, run)
    if target.exists() or not findings:
        return
    screened_out: list[str] = []
    if prefilter:
        # Two-stage comb: this comb sees only what the first comb kept; the rest count as DROP.
        first = json.loads((HERE / "out" / prefilter / target.name).read_text())
        kept = {first["refs"][fid] for fid, (decision, _) in first["decisions"].items() if decision == "KEEP"}
        screened_out = [x["ref"] for x in findings if x["ref"] not in kept]
        findings = [x for x in findings if x["ref"] in kept]
    repo, base, head = load_cases()[case]
    worktree = Path(os.environ["COMB_WT"]) / case
    if not worktree.is_dir():
        raise SystemExit(f"missing worktree {worktree}")
    model, profile = resolve_model_alias(alias)
    if profile is None:
        raise SystemExit(f"alias {alias!r} has no profile")
    inputs = {
        "findings": render(findings),
        "changed_files": changed_files(repo, base, head),
        "cwd": str(worktree),
    }
    decisions: dict[str, tuple[str, str]] = {}
    refs = {f"F{n}": x["ref"] for n, x in enumerate(findings, 1)}
    started = time.monotonic()
    result = None
    if findings:
        async with sem:
            started = time.monotonic()
            result = await run_review_with_profile(
                load_template(HERE / "comb.yaml"), inputs,
                profile=profile, model=model, effort=model_effort(alias), alias=alias,
            )
        for line in result.raw_output.splitlines():
            if (m := DECISION.search(line)) and m.group(1).upper() not in decisions:
                decisions[m.group(1).upper()] = (m.group(2).upper(), m.group(3).strip())
    for n, ref in enumerate(screened_out, 1):
        refs[f"P{n}"] = ref
        decisions[f"P{n}"] = ("DROP", f"dropped by {prefilter}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "case": case, "reviewer": reviewer, "run": run, "comb": label,
        "refs": refs,
        "decisions": decisions,
        "wall_seconds": round(time.monotonic() - started, 1),
        "duration_seconds": result.duration_seconds if result else 0,
        "cost_usd": result.cost_usd if result else 0,
        "effort": str(result.effort) if result and result.effort else None,
        "tool_calls_made": result.tool_calls_made if result else 0,
        "recovery_turn_used": result.recovery_turn_used if result else False,
        "usage": str(result.usage) if result else None,
        "raw_output": result.raw_output if result else "",
    }, indent=1))
    print(f"{alias} {case} {reviewer} {run}: {len(decisions)}/{len(findings)} decided", flush=True)


async def run_all(
    alias: str, runs: list[str], jobs: int, only_case: str | None, prefilter: str | None
) -> None:
    sem = asyncio.Semaphore(jobs)
    tasks = [
        comb_one(alias, case, reviewer, run, sem, prefilter)
        for case in load_cases() if only_case in (None, case)
        for reviewer in REVIEWERS for run in runs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            print(f"ERROR {type(r).__name__}: {r}", flush=True)


def score() -> None:
    grades = load_grades()
    rows = collections.defaultdict(collections.Counter)
    for path in sorted((HERE / "out").glob("*/*.json")):
        d = json.loads(path.read_text())
        key = (d["comb"], d["reviewer"])
        rows[key]["calls"] += 1
        rows[key]["seconds"] += d["duration_seconds"] or 0
        for fid, ref in d["refs"].items():
            real = grades[(d["case"], ref)] == "REAL"
            decision = d["decisions"].get(fid, ("MISSING",))[0]
            rows[key][f"{'real' if real else 'other'}_{decision.lower()}"] += 1
    print("| Comb | Reviewer | Calls | REAL kept | REAL dropped | Other dropped | Other kept |"
          " Undecided | Precision after | Mean s/call |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for (comb, reviewer), c in sorted(rows.items()):
        kept = c["real_keep"] + c["other_keep"]
        precision = f"{c['real_keep'] / kept:.0%}" if kept else "n/a"
        undecided = c["real_missing"] + c["other_missing"]
        print(f"| {comb} | {reviewer} | {c['calls']} | {c['real_keep']} | {c['real_drop']} |"
              f" {c['other_drop']} | {c['other_keep']} | {undecided} | {precision} |"
              f" {c['seconds'] / max(c['calls'], 1):.0f} |")


def load_known() -> set[tuple[str, str]]:
    """(case, ref) pairs whose issue is one of the case's known bugs (B*), not a control."""
    known = set()
    for path in (GRID / "precision").glob("*-graded.json"):
        data = json.loads(path.read_text())
        for issue in data["issues"]:
            if (issue.get("known") or "").startswith("B"):
                known.update((data["case"], ref) for ref in issue["members"])
    return known


def quality() -> None:
    """Per reviewer: the raw review against the same review after each comb (run 1 only)."""
    grades, known = load_grades(), load_known()
    combs = sorted(p.name for p in (HERE / "out").iterdir() if p.is_dir())
    print("\n| Reviewer | Output | Findings | REAL | Precision | Known bugs |")
    print("|---|---|---|---|---|---|")
    for reviewer in REVIEWERS:
        raw = [(case, x["ref"]) for case in load_cases()
               for x in review_findings(case, reviewer, "1")]
        real = sum(grades[k] == "REAL" for k in raw)
        print(f"| {reviewer} | raw | {len(raw)} | {real} | {real / len(raw):.0%} |"
              f" {sum(k in known for k in raw)} |")
        for comb in combs:
            outs = [json.loads(p.read_text()) for p in (HERE / "out" / comb).glob(f"*-{reviewer}-1.json")]
            if len(outs) < len(load_cases()):
                continue  # incomplete comb: skip rather than compare unequal sets
            kept = [(d["case"], ref) for d in outs for fid, ref in d["refs"].items()
                    if d["decisions"].get(fid, ("",))[0] == "KEEP"]
            real_kept = sum(grades[k] == "REAL" for k in kept)
            precision = f"{real_kept / len(kept):.0%}" if kept else "n/a"
            print(f"| | after {comb} | {len(kept)} | {real_kept} | {precision} |"
                  f" {sum(k in known for k in kept)} |")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("alias")
    run.add_argument("--runs", default="1")
    run.add_argument("--jobs", type=int, default=3)
    run.add_argument("--case")
    run.add_argument("--after", help="two-stage: comb only what this earlier comb kept")
    sub.add_parser("score")
    args = parser.parse_args()
    if args.cmd == "score":
        score()
        quality()
        return
    asyncio.run(run_all(args.alias, args.runs.split(","), args.jobs, args.case, args.after))


if __name__ == "__main__":
    main()
