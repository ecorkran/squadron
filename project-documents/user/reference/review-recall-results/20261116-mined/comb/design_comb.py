"""Comb design reviews of the 43 mined cases and score the result against the graded flaw hits.

Usage: design_comb.py run <comb-alias> --reviewers haiku-xhigh,fable-medium --runs 1,2,3 [--jobs 4] [--case C]
       design_comb.py score

A comb call sees one review's CONCERN/FAIL findings, the document, and its parent (from wt/<case>).
Truth is the graded flaw hits (grade/, grade2/): a finding is "real" if it hit one of the 82 flaws.
Findings that are valid but not among the 82 count as noise, so precision is a lower bound.
"""
from __future__ import annotations

import argparse, asyncio, collections, json, re, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MINED = HERE.parent
COMBED = ("CONCERN", "FAIL")
DECISION = re.compile(r"\b(F\d+)\b\W{0,6}(KEEP|DROP)\b\W*(.*)", re.IGNORECASE)
NO_VERDICT_REASON = "no verdict from comb; default DROP"
GRADE_SETS = (("grade", "map.json", None), ("grade2", "map.json", None), ("grade3", "map.json", None))


def load_cases() -> dict[str, tuple[str, str]]:
    """case -> (document path, parent path)."""
    out = {}
    for line in (MINED / "against.tsv").read_text().splitlines():
        case, _kind, doc, against = line.split("\t")
        out[case] = (doc, against)
    return out


def review_path(case: str, alias: str, run: str) -> Path:
    return MINED / "out" / f"{case}-{alias}-{run}.json"


def combed_findings(case: str, alias: str, run: str) -> list[dict]:
    review = json.loads(review_path(case, alias, run).read_text())
    return [dict(f, i=i) for i, f in enumerate(review["findings"]) if f["severity"] in COMBED]


def load_hits() -> set[tuple[str, str, str, int]]:
    """(case, alias, run, finding index) for every finding that hit a graded flaw."""
    hits = set()
    for grade_dir, map_file, _ in GRADE_SETS:
        mapping = json.loads((MINED / grade_dir / map_file).read_text())
        for case_dir in (MINED / grade_dir).iterdir():
            path = case_dir / "hits.json"
            if not path.exists():
                continue
            for flaw in json.loads(path.read_text())["flaws"]:
                for rid, indexes in flaw["hits"].items():
                    m = mapping[f"{case_dir.name}/{rid}"]
                    hits.update((case_dir.name, m["alias"], str(m["run"]), i) for i in indexes)
    return hits


def load_flaw_hits() -> dict[tuple[str, str, str, int], set[str]]:
    """(case, alias, run, index) -> flaw ids hit, for union-of-kept recall."""
    out: dict = collections.defaultdict(set)
    for grade_dir, map_file, _ in GRADE_SETS:
        mapping = json.loads((MINED / grade_dir / map_file).read_text())
        for case_dir in (MINED / grade_dir).iterdir():
            path = case_dir / "hits.json"
            if not path.exists():
                continue
            for flaw in json.loads(path.read_text())["flaws"]:
                for rid, indexes in flaw["hits"].items():
                    m = mapping[f"{case_dir.name}/{rid}"]
                    for i in indexes:
                        out[(case_dir.name, m["alias"], str(m["run"]), i)].add(f"{case_dir.name}/{flaw['id']}")
    return out


def render(findings: list[dict]) -> str:
    return "\n\n".join(
        f"### F{n} [{f['severity']}] {f['title']}\nLocation: {f.get('location')}\n\n{f['description']}"
        for n, f in enumerate(findings, 1)
    )


async def comb_one(comb: str, case: str, alias: str, run: str, sem: asyncio.Semaphore) -> None:
    from squadron.models.aliases import model_effort, resolve_model_alias
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import load_template

    target = HERE / "out" / comb / f"{case}-{alias}-{run}.json"
    findings = combed_findings(case, alias, run)
    if target.exists() or not findings:
        return
    doc, parent = load_cases()[case]
    worktree = MINED / "wt" / case
    if not worktree.is_dir():
        raise SystemExit(f"missing worktree {worktree}")
    model, profile = resolve_model_alias(comb)
    if profile is None:
        raise SystemExit(f"alias {comb!r} has no profile")
    inputs = {"findings": render(findings), "changed_files": f"{doc}\n{parent}", "cwd": str(worktree)}
    refs = {f"F{n}": f["i"] for n, f in enumerate(findings, 1)}
    async with sem:
        started = time.monotonic()
        result = await run_review_with_profile(
            load_template(HERE / "design_comb.yaml"), inputs,
            profile=profile, model=model, effort=model_effort(comb), alias=comb,
        )
    decisions: dict[str, tuple[str, str]] = {}
    for line in result.raw_output.splitlines():
        if (m := DECISION.search(line)) and m.group(1).upper() not in decisions:
            decisions[m.group(1).upper()] = (m.group(2).upper(), m.group(3).strip())
    defaulted = [fid for fid in refs if fid not in decisions]
    for fid in defaulted:
        decisions[fid] = ("DROP", NO_VERDICT_REASON)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "case": case, "reviewer": alias, "run": run, "comb": comb, "refs": refs, "decisions": decisions,
        "wall_seconds": round(time.monotonic() - started, 1),
        "cost_usd": result.cost_usd, "raw_output": result.raw_output,
    }, indent=1))
    print(f"{comb} {case} {alias} {run}: {len(findings) - len(defaulted)}/{len(findings)} parsed", flush=True)


async def run_all(comb: str, reviewers: list[str], runs: list[str], jobs: int, only: str | None) -> None:
    sem = asyncio.Semaphore(jobs)
    results = await asyncio.gather(
        *(comb_one(comb, c, a, r, sem) for c in load_cases() if only in (None, c) for a in reviewers for r in runs),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, BaseException):
            print(f"ERROR {type(r).__name__}: {r}", flush=True)


def score() -> None:
    hits, flaw_hits = load_hits(), load_flaw_hits()
    combs = sorted(p.name for p in (HERE / "out").iterdir() if p.is_dir())
    print("| Reviewer | Output | Findings | Real | Precision | Flaws (sum over runs) |")
    print("|---|---|---|---|---|---|")
    reviewers = sorted({json.loads(p.read_text())["reviewer"] for c in combs for p in (HERE / "out" / c).glob("*.json")})
    for alias in reviewers:
        for label in ["raw"] + combs:
            kept, flaws = [], set()
            for case in load_cases():
                for run in ("1", "2", "3"):
                    if not review_path(case, alias, run).exists():
                        continue
                    findings = combed_findings(case, alias, run)
                    if label == "raw":
                        picked = [f["i"] for f in findings]
                    else:
                        path = HERE / "out" / label / f"{case}-{alias}-{run}.json"
                        if not path.exists():
                            continue
                        d = json.loads(path.read_text())
                        picked = [d["refs"][fid] for fid, (dec, _) in d["decisions"].items() if dec == "KEEP"]
                    for i in picked:
                        kept.append((case, alias, run, i))
                        flaws |= {(run, x) for x in flaw_hits.get((case, alias, run, i), ())}
            real = sum(k in hits for k in kept)
            print(f"| {alias} | {label} | {len(kept)} | {real} | {real / len(kept):.0%} | {len(flaws)} |"
                  if kept else f"| {alias} | {label} | 0 | 0 | n/a | 0 |")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("alias")
    r.add_argument("--reviewers", default="haiku-xhigh,fable-medium")
    r.add_argument("--runs", default="1,2,3")
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--case")
    sub.add_parser("score")
    a = p.parse_args()
    if a.cmd == "score":
        score()
    else:
        asyncio.run(run_all(a.alias, a.reviewers.split(","), a.runs.split(","), a.jobs, a.case))


if __name__ == "__main__":
    main()
