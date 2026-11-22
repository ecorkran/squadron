"""Grader checks with no reading: credit given to reviews that could not have read code, and
whether hits track output length. Run after build.py, an5.py, b1.py (reads their json in cwd)."""
import json, math, collections, statistics as st
import numpy as np
R = json.load(open("reviews.json")); F = json.load(open("flaws2.json")); DF = json.load(open("design_findings.json"))
def need(s):
    s = s.lower().strip()
    if s.startswith("code") or s.startswith("doc plus the regex"): return "code"
    if s.startswith("doc alone") or s.startswith("document alone"): return "doc"
    return "doc+doc"
for f in F.values(): f["need"] = need(f["needs"])
print("1. 'needs code' credit by tool calls made (reviews got paths only, so the first calls open the document and its parent)")
for lab, sel in (("Claude", lambda a: a.split("-")[0] in ("haiku", "opus", "fable", "sonnet")), ("others", lambda a: a.split("-")[0] not in ("haiku", "opus", "fable", "sonnet"))):
    for tc in (0, 1, 2, 3):
        rs = [r for r in R if sel(r["alias"]) and r["tool_calls"] == tc]
        tot = hit = 0; who = collections.Counter()
        for r in rs:
            for k, f in F.items():
                c, fid = k.split("/")
                if c == r["case"] and f["need"] == "code":
                    tot += 1
                    if fid in r["hit"]: hit += 1; who[(r["alias"], k)] += 1
        print(f"  {lab:7} {tc} calls: {len(rs):3} reviews, code-needing flaws credited {hit}/{tot}", dict(who) if 0 < hit <= 8 else "")
print("\n2. hits against output volume, same model and same flaw (per doubling)")
obs = []
for r in R:
    fs = [f for f in DF.get(f"{r['alias']}#{r['run']}", []) if f["case"] == r["case"]]
    for k, f in F.items():
        c, fid = k.split("/")
        if c == r["case"]:
            obs.append(dict(flaw=k, alias=r["alias"], hit=int(fid in r["hit"]), tc=r["tool_calls"], comp=r["completion"], nfind=len(fs), need=f["need"]))
def fe(rows, xs, groups=("flaw", "alias")):
    rows = [o for o in rows if all(o[x] for x in xs)]
    y = np.array([o["hit"] for o in rows], float); X = np.log2(np.array([[o[x] for x in xs] for o in rows], float))
    for _ in range(40):
        for g in groups:
            idx = collections.defaultdict(list)
            for i, o in enumerate(rows): idx[o[g]].append(i)
            for ii in idx.values(): y[ii] -= y[ii].mean(); X[ii] -= X[ii].mean(axis=0)
    b, *_ = np.linalg.lstsq(X, y, rcond=None); res = y - X @ b
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (res @ res) / (len(y) - len(xs)))
    return "  ".join(f"{x} {bi:+.3f}±{si:.3f}" for x, bi, si in zip(xs, b, se)) + f"  (n={len(y)})"
for n in ("doc", "doc+doc", "code"):
    rows = [o for o in obs if o["need"] == n]
    print(f"  {n:8} alone: {fe(rows, ['comp'])} | {fe(rows, ['nfind'])}")
    print(f"  {n:8} joint: {fe(rows, ['tc', 'comp', 'nfind'])}")
print("  haiku-xhigh only, by output-token third (hit rate on doc-alone / code-needing flaws):")
hk = [o for o in obs if o["alias"] == "haiku-xhigh" and o["comp"]]; cs = sorted(o["comp"] for o in hk); t1, t2 = cs[len(cs) // 3], cs[2 * len(cs) // 3]
for lab, lo, hi in ((f"<{t1 // 1000}k", 0, t1), (f"{t1 // 1000}-{t2 // 1000}k", t1, t2), (f">{t2 // 1000}k", t2, 10**9)):
    print(f"    {lab:10}", "  ".join(f"{n}: {st.mean([o['hit'] for o in hk if lo <= o['comp'] < hi and o['need'] == n]):.0%}" for n in ("doc", "code")))
