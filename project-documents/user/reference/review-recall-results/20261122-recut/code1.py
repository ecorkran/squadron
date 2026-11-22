import json, glob, collections, statistics as st, random, os
sev = {}; per = collections.defaultdict(lambda: collections.Counter()); issues = []
for f in glob.glob("precision/*-findings.json"):
    case = os.path.basename(f).split("-")[0]
    for x in json.load(open(f)): sev[(case, x["ref"])] = x["severity"]
for f in glob.glob("precision/*-graded.json"):
    d = json.load(open(f))
    for i in d["issues"]:
        issues.append(i)
        for ref in i["members"]:
            cfg, run, _ = ref.split("/")
            per[(d["case"], cfg, run)][i["grade"]] += 1
            if i.get("known"): per[(d["case"], cfg, run)]["known"] += 1
            per[("SEV", cfg, sev.get((d["case"], ref), "?"))][i["grade"]] += 1
print("severity label vs grade (code grid 2):")
for cfg in ("haiku-xhigh", "sol", "sonnet-high", "sonnet"):
    for s in ("FAIL", "CONCERN"):
        c = per[("SEV", cfg, s)]; n = sum(c.values())
        print(f"  {cfg:12} {s:8} n={n:4}  REAL {c['REAL'] / n if n else 0:.0%}  MINOR {c['MINOR'] / n if n else 0:.0%}")
    r = {s: per[("SEV", cfg, s)]["REAL"] for s in ("FAIL", "CONCERN")}
    print(f"  {cfg:12} share of REAL findings labelled FAIL: {r['FAIL'] / max(1, sum(r.values())):.0%}")
print("\nREAL findings per review by tool calls (code):")
rows = []
for f in glob.glob("*.json"):
    parts = f[:-5].rsplit("-", 1); case, cfg = parts[0].split("-", 1); run = parts[1]
    d = json.load(open(f)); c = per.get((case, cfg, run))
    if cfg in ("haiku-xhigh", "sol", "sonnet-high", "sonnet"):
        rows.append((cfg, case, d.get("tool_calls_made"), d.get("completion_tokens"), d.get("duration_seconds"), (c or {}).get("REAL", 0), (c or {}).get("MINOR", 0)))
for cfg in ("haiku-xhigh", "sonnet-high", "sonnet", "sol"):
    rs = [r for r in rows if r[0] == cfg]
    print(f"  {cfg:12} n={len(rs)} med tools={st.median([r[2] for r in rs if r[2] is not None]) if any(r[2] is not None for r in rs) else None} REAL/review={st.mean(r[5] for r in rs):.1f} MINOR/review={st.mean(r[6] for r in rs):.1f}")
    for lo, hi in ((0, 5), (6, 15), (16, 30), (31, 60), (61, 999)):
        b = [r for r in rs if r[2] is not None and lo <= r[2] <= hi]
        if b: print(f"      tools {lo}-{hi}: n={len(b)} REAL/review {st.mean(r[5] for r in b):.1f}  MINOR/review {st.mean(r[6] for r in b):.1f}")
random.seed(3)
print("\nsample MINOR issue titles:"); [print("  -", i["title"][:150]) for i in random.sample([i for i in issues if i["grade"] == "MINOR"], 22)]
print("\nsample REAL issue titles:"); [print("  -", i["title"][:150]) for i in random.sample([i for i in issues if i["grade"] == "REAL"], 12)]
