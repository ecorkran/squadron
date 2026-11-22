"""Does Chao's estimate (S + f1^2 / 2 f2) track the flaws left unfound? Keyed hits stand in for a perfect comb."""
import json, collections, statistics as st, random, glob, os
R = json.load(open("reviews.json")); F = json.load(open("flaws2.json"))
hit = collections.defaultdict(set); cases = collections.defaultdict(set)
for r in R:
    k = (r["alias"], r["run"]); cases[k].add(r["case"]); hit[k] |= {f"{r['case']}/{fid}" for fid in r["hit"]}
full = sorted(k for k in hit if len(cases[k]) == 43)
def chao(counts):
    S = sum(1 for c in counts if c); f1 = sum(1 for c in counts if c == 1); f2 = sum(1 for c in counts if c == 2)
    return S, f1, f2, S + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)
def counts(members, keys): return [sum(1 for m in members if k in hit[m]) for k in keys]
ALL = sorted(F); CASES = sorted({k.split("/")[0] for k in F})
print("pooled over the 43 documents (true total 82 keyed flaws):")
for name, ms in (("4 cheap", [("haiku-xhigh", 1), ("minimax31-flash", 1), ("hy4", 1), ("mimo", 1)]), ("haiku-xhigh x3", [("haiku-xhigh", r) for r in (1, 2, 3)]),
                 ("fable-medium x3", [("fable-medium", r) for r in (1, 2, 3)]), ("opus-high x3", [("opus-high", r) for r in (1, 2, 3)]), ("sonnet high+medium", [("sonnet-high", 1), ("sonnet-medium", 1)]), ("all 27 full-set runs", full)):
    S, f1, f2, N = chao(counts(ms, ALL)); print(f"  {name:22} found {S:2}  once {f1:2}  twice {f2:2}  estimate {N:5.1f}  (truly left {82 - S}, estimate says {N - S:.1f})")
random.seed(5); ratios = []; pairs = []
for _ in range(400):
    ms = random.sample(full, 4); S, f1, f2, N = chao(counts(ms, ALL)); ratios.append(N / 82); pairs.append((N - S, 82 - S))
print(f"  random sets of 4 (400 draws): estimate / truth median {st.median(ratios):.2f}, 10th-90th pct {sorted(ratios)[40]:.2f}-{sorted(ratios)[360]:.2f}; correlation of estimated-left with truly-left {st.correlation([a for a, b in pairs], [b for a, b in pairs]):.2f}")
print("\nper document, 4 cheap: does the estimate pick out the documents with flaws left?")
ms = [("haiku-xhigh", 1), ("minimax31-flash", 1), ("hy4", 1), ("mimo", 1)]; rows = []
for c in CASES:
    keys = [k for k in ALL if k.startswith(c + "/")]; S, f1, f2, N = chao(counts(ms, keys)); rows.append((N - S, len(keys) - S, f1, S))
flag = [r for r in rows if r[0] >= 1]; clean = [r for r in rows if r[0] < 1]
print(f"  estimate says >=1 left: {len(flag)} docs, truly left mean {st.mean(r[1] for r in flag):.2f}, docs with something left {sum(1 for r in flag if r[1])}/{len(flag)}")
print(f"  estimate says none left: {len(clean)} docs, truly left mean {st.mean(r[1] for r in clean):.2f}, docs with something left {sum(1 for r in clean if r[1])}/{len(clean)}")
one = [r for r in rows if r[2] >= 1]; none = [r for r in rows if r[2] == 0]
print(f"  simpler rule, any flaw found by exactly one reviewer: {len(one)} docs, something left in {sum(1 for r in one if r[1])}; no singletons: {len(none)} docs, something left in {sum(1 for r in none if r[1])}")
# code grid 2: graded issue clusters
P = "/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261112-grid2/precision/"; issues = []
for f in glob.glob(P + "*-graded.json"):
    for i in json.load(open(f))["issues"]: i["m"] = {tuple(r.split("/")[:2]) for r in i["members"]}; issues.append(i)
print("\ncode grid 2 (41 REAL issues found by all 12 reviews; 221 issues of any grade):")
for name, ms in (("haiku x3", {("haiku-xhigh", str(r)) for r in (1, 2, 3)}), ("sol x3", {("sol", str(r)) for r in (1, 2, 3)}), ("haiku + sol", {("haiku-xhigh", "1"), ("sol", "1")}), ("haiku x3 + sol x3", {(a, str(r)) for a in ("haiku-xhigh", "sol") for r in (1, 2, 3)})):
    for lab, pool in (("REAL only (after a perfect comb)", [i for i in issues if i["grade"] == "REAL"]), ("everything (no comb)", issues)):
        S, f1, f2, N = chao([len(ms & i["m"]) for i in pool]); print(f"  {name:18} {lab:33} found {S:3} once {f1:3} twice {f2:3} estimate {N:6.1f} of {len(pool)}")
