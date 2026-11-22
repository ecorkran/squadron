import json, math, collections, statistics as st
import numpy as np
R = json.load(open("reviews.json")); F = json.load(open("flaws.json"))
def needs(s):
    s = s.lower()
    if "code" in s: return "code"
    if "parent" in s or "plus" in s or "plan" in s or "arch" in s: return "doc+parent"
    return "doc alone"
obs = []  # one row per (review, flaw)
for r in R:
    hit = set(r["hit"])
    for k, f in F.items():
        c, fid = k.split("/")
        if c != r["case"]: continue
        obs.append(dict(flaw=k, alias=r["alias"], hit=int(fid in hit), tc=r["tool_calls"], comp=r["completion"], dur=r["dur"],
                        need=needs(f["needs"]), kind=f["kind"], sdk=r["alias"].split("-")[0] in ("haiku", "opus", "fable", "sonnet")))
print("obs", len(obs), collections.Counter(needs(f["needs"]) for f in F.values()))

def fe_slope(rows, xkey, groups):
    """Slope of hit on log(x) after removing group means (linear probability)."""
    rows = [o for o in rows if o[xkey]]
    y = np.array([o["hit"] for o in rows], float); x = np.log(np.array([o[xkey] for o in rows], float))
    for _ in range(30):
        for g in groups:
            idx = collections.defaultdict(list)
            for i, o in enumerate(rows): idx[o[g]].append(i)
            for ii in idx.values():
                y[ii] -= y[ii].mean(); x[ii] -= x[ii].mean()
    b = (x @ y) / (x @ x); res = y - b * x
    se = math.sqrt((res @ res) / (len(y) - 1) / (x @ x))
    return b, se, len(y)
for label, rows in (("all configs", obs), ("claude only", [o for o in obs if o["sdk"]]), ("non-claude", [o for o in obs if not o["sdk"]])):
    for x in ("tc", "comp", "dur"):
        b1, s1, n = fe_slope(rows, x, ["flaw"]); b2, s2, _ = fe_slope(rows, x, ["flaw", "alias"])
        print(f"{label:12} {x:5} n={n:5}  across models: {b1 * math.log(2):+.3f}±{s1 * math.log(2):.3f} per doubling   within model: {b2 * math.log(2):+.3f}±{s2 * math.log(2):.3f}")

print("\nhit rate by what the flaw needs")
cfgs = ["fable-high", "fable-medium", "haiku-xhigh", "opus-high", "opus-medium", "sonnet-high", "sonnet-medium", "hy4", "minimax31-flash", "glm-flash", "deepseek4-flash", "mimo"]
print(f"{'config':16}" + "".join(f"{n:>12}" for n in ("doc alone", "doc+parent", "code")))
for a in cfgs:
    line = f"{a:16}"
    for n in ("doc alone", "doc+parent", "code"):
        xs = [o["hit"] for o in obs if o["alias"] == a and o["need"] == n]
        line += f"{st.mean(xs):>9.0%}/{len(xs):<3}" if xs else " " * 12
    print(line)
