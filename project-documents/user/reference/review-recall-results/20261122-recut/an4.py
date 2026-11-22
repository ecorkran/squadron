import json, math, collections, statistics as st
import numpy as np
R = json.load(open("reviews.json")); F = json.load(open("flaws.json"))
def needs(s):
    s = s.lower().strip()
    if s.startswith("code") or s.startswith("doc plus the regex"): return "code"
    if s.startswith("doc alone") or s.startswith("document alone"): return "doc alone"
    return "doc+other doc"
for f in F.values(): f["need"] = needs(f["needs"])
print(collections.Counter(f["need"] for f in F.values()))
obs = []
for r in R:
    hit = set(r["hit"])
    for k, f in F.items():
        c, fid = k.split("/")
        if c == r["case"]:
            obs.append(dict(flaw=k, alias=r["alias"], run=r["run"], hit=int(fid in hit), tc=r["tool_calls"], comp=r["completion"], dur=r["dur"], need=f["need"], kind=f["kind"]))
NEEDS = ("doc alone", "doc+other doc", "code")
cfgs = ["fable-high", "fable-medium", "haiku-xhigh", "opus-high", "opus-medium", "sonnet-high", "sonnet-medium", "hy4", "minimax31-flash", "qwen38-flash", "glm-flash", "deepseek4-flash", "mimo", "hy4-flash"]
print(f"\n{'config':16}" + "".join(f"{n:>15}" for n in NEEDS) + "   med tool calls")
for a in cfgs:
    line = f"{a:16}"
    for n in NEEDS:
        xs = [o["hit"] for o in obs if o["alias"] == a and o["need"] == n]
        line += f"{st.mean(xs):>11.0%}/{len(xs):<3}"
    print(line, "  ", st.median(r["tool_calls"] for r in R if r["alias"] == a and r["tool_calls"] is not None))

def fe_slope(rows, xkey, groups):
    rows = [o for o in rows if o[xkey]]
    y = np.array([o["hit"] for o in rows], float); x = np.log2(np.array([o[xkey] for o in rows], float))
    for _ in range(30):
        for g in groups:
            idx = collections.defaultdict(list)
            for i, o in enumerate(rows): idx[o[g]].append(i)
            for ii in idx.values():
                y[ii] -= y[ii].mean(); x[ii] -= x[ii].mean()
    b = (x @ y) / (x @ x); res = y - b * x
    return b, math.sqrt((res @ res) / (len(y) - 1) / (x @ x)), len(y)
print("\nchange in hit probability per doubling, same model and same flaw (flaw + model fixed effects)")
for n in NEEDS:
    rows = [o for o in obs if o["need"] == n]
    print(f"  {n:14}", "  ".join(f"{x}: {fe_slope(rows, x, ['flaw', 'alias'])[0]:+.3f}±{fe_slope(rows, x, ['flaw', 'alias'])[1]:.3f}" for x in ("tc", "comp", "dur")))

print("\nhaiku-xhigh and all-Claude reviews bucketed by tool calls: hit rate (n flaw-observations)")
CL = ("haiku-xhigh", "opus-high", "opus-medium", "fable-medium", "fable-high", "sonnet-high", "sonnet-medium")
for label, sel in (("haiku-xhigh", ("haiku-xhigh",)), ("all Claude", CL), ("non-Claude", None)):
    print(" ", label)
    for lo, hi in ((0, 3), (4, 7), (8, 15), (16, 30), (31, 999)):
        line = f"    {lo:>3}-{hi:<4}"
        for n in NEEDS:
            xs = [o["hit"] for o in obs if (o["alias"] in sel if sel else o["alias"] not in CL) and o["need"] == n and o["tc"] is not None and lo <= o["tc"] <= hi]
            line += f"{(st.mean(xs) if xs else float('nan')):>11.0%}/{len(xs):<4}"
        print(line)

print("\nflaws never hit by any review:")
for k, f in F.items():
    if not any(o["hit"] for o in obs if o["flaw"] == k):
        print(f"  [{f['kind']}/{f['need']}] {k}: {f['text'][:230]}")
