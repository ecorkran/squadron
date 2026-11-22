"""Comb each finished review with one comb model, using the code comb prompt of 20261113-comb: comb.py COMB_ALIAS REVIEWER[,REVIEWER] [JOBS] [FIRST_COMB].

With FIRST_COMB the comb sees only what that earlier comb kept (a two-stage comb) and writes to comb/<FIRST_COMB>+<COMB_ALIAS>/.

One call per review, over its CONCERN/FAIL findings, with the sandbox at head as the working directory.
Writes comb/<comb-alias>/<case>-<reviewer>-1.json with the kept finding indexes.
"""
import asyncio, json, pathlib, re, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
import os
# COMB_TEMPLATE swaps the comb prompt and COMB_LABEL names its output folder; COMB_CATEGORIES limits the findings combed.
TEMPLATE = pathlib.Path(os.environ["COMB_TEMPLATE"]) if "COMB_TEMPLATE" in os.environ else HERE.parent / "20261113-comb" / "comb.yaml"
LABEL = os.environ.get("COMB_LABEL")
CATEGORIES = set(os.environ["COMB_CATEGORIES"].split(",")) if "COMB_CATEGORIES" in os.environ else None
DECISION = re.compile(r"\b(F\d+)\b\W{0,6}(KEEP|DROP)\b\W*(.*)", re.IGNORECASE)
ACTED_ON = ("CONCERN", "FAIL")
async def comb_one(alias: str, case: dict, reviewer: str, sem: asyncio.Semaphore, first: str | None) -> None:
    from squadron.models.aliases import model_effort, resolve_model_alias
    from squadron.review.review_client import run_review_with_profile
    from squadron.review.templates import load_template
    source = HERE / "out" / f"{case['name']}-{reviewer}-1.json"
    target = HERE / "comb" / (LABEL or (f"{first}+{alias}" if first else alias)) / source.name
    first_path = HERE / "comb" / first / source.name if first else None
    if target.exists() or not source.exists() or (first_path and not first_path.exists()):
        return
    allowed = set(json.loads(first_path.read_text())["kept"]) if first_path else None
    findings = [(i, f) for i, f in enumerate(json.loads(source.read_text())["findings"]) if str(f.get("severity", "")).upper() in ACTED_ON and (allowed is None or i in allowed) and (CATEGORIES is None or str(f.get("category")) in CATEGORIES)]
    decisions: dict[str, list[str]] = {}
    cost = 0.0
    if findings:
        refs = {f"F{n}": i for n, (i, _) in enumerate(findings, 1)}
        text = "\n\n".join(f"### F{n} [{f['severity']}] {f['title']}\nLocation: {f.get('location')}\n\n{f['description']}" for n, (_, f) in enumerate(findings, 1))
        changed = subprocess.run(["git", "-C", case["sandbox"], "diff", "--name-only", case["base_local"], "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        model, profile = resolve_model_alias(alias)
        if profile is None:
            raise SystemExit(f"alias {alias!r} has no profile")
        async with sem:
            result = await run_review_with_profile(load_template(TEMPLATE), {"findings": text, "changed_files": changed, "cwd": case["sandbox"]},
                                                   profile=profile, model=model, effort=model_effort(alias), alias=alias)
        cost = result.cost_usd or 0.0
        for line in result.raw_output.splitlines():
            if (m := DECISION.search(line)) and m.group(1).upper() not in decisions:
                decisions[m.group(1).upper()] = [m.group(2).upper(), m.group(3).strip()]
        unjudged = [fid for fid in refs if fid not in decisions]
        kept = sorted(refs[fid] for fid, (verdict, _) in decisions.items() if fid in refs and verdict == "KEEP")
    else:
        refs, unjudged, kept = {}, [], []
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"case": case["name"], "reviewer": reviewer, "comb": alias, "refs": refs, "decisions": decisions, "unjudged": unjudged, "kept": kept, "cost_usd": cost}, indent=1))
    print(f"{alias} {case['name']} {reviewer}: kept {len(kept)} of {len(findings)}, no verdict {len(unjudged)}", flush=True)
async def main() -> None:
    alias, reviewers = sys.argv[1], sys.argv[2].split(",")
    sem = asyncio.Semaphore(int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    cases = list(json.load(open(HERE / "cases.json")).values())
    first = sys.argv[4] if len(sys.argv) > 4 else None
    results = await asyncio.gather(*(comb_one(alias, c, r, sem, first) for c in cases for r in reviewers), return_exceptions=True)
    failed = [r for r in results if isinstance(r, BaseException)]
    print(f"calls failed: {len(failed)}", *[repr(f)[:200] for f in failed[:5]], sep="\n")
asyncio.run(main())
