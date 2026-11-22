"""Code review, grid 3 run 1 (10 original cases, 14 known bugs): single configs and unions of 2-4, with cost per review."""
import importlib.util, pathlib, collections, itertools
G3 = pathlib.Path(__file__).resolve().parent.parent / "20261113-grid3" / "precision"
spec = importlib.util.spec_from_file_location("score", G3 / "score.py"); score = importlib.util.module_from_spec(spec); spec.loader.exec_module(score)
by_ref = score.load()
# cost per review from RESULTS.md section 3 (sub = API-equivalent on subscription; sol on the Codex plan from section 1)
COST = {"haiku-xhigh": 0.53, "sol": 0.02, "sol-r": 0.24, "hy4": 0.35, "luna-r-high": 0.04, "luna-r-xhigh": 0.06, "minimax31-flash": 0.06,
        "sonnet-high": 0.52, "deepseek4-flash": 0.12, "sonnet": 0.50}
real = collections.defaultdict(set); known = collections.defaultdict(set); nfind = collections.Counter(); cases = collections.defaultdict(set)
for (case, ref), issue in by_ref.items():
    cfg, run, _ = ref.split("/")
    if run != "1" or case not in score.ORIGINAL: continue
    nfind[cfg] += 1; cases[cfg].add(case)
    if issue["grade"] == "REAL": real[cfg].add((case, issue["id"]))
    if str(issue.get("known") or "").startswith("B"): known[cfg].add((case, issue["known"]))
allreal = set().union(*real.values()); allknown = set().union(*known.values())
print(f"found by any config in run 1: {len(allreal)} REAL issues, {len(allknown)} of 14 known bugs")
print(f"{'config':18}{'cases':>6}{'findings':>9}{'REAL':>6}{'%real':>7}{'known/14':>9}{'$':>6}")
for c in sorted(nfind, key=lambda c: -len(known[c]) * 100 - len(real[c])):
    print(f"{c:18}{len(cases[c]):>6}{nfind[c]:>9}{len(real[c]):>6}{len(real[c]) / nfind[c]:>7.0%}{len(known[c]):>9}{COST.get(c, float('nan')):>6.2f}")
pool = [c for c in COST if c in nfind and len(cases[c]) >= 9]
print("\nbest unions by known bugs, then REAL issues (run 1 each):")
for n in (2, 3, 4):
    rows = sorted(((len(set().union(*(known[c] for c in cb))), len(set().union(*(real[c] for c in cb))), -sum(COST[c] for c in cb), cb) for cb in itertools.combinations(pool, n)), reverse=True)
    for k, r, negc, cb in rows[:3]:
        f = sum(nfind[c] for c in cb); print(f"  {n}: known {k}/14  REAL {r}  findings/case {f / 10:.1f}  ${-negc:.2f}  {' + '.join(cb)}")
for name, cb in (("haiku-xhigh + sol", ("haiku-xhigh", "sol")), ("cheap 4: minimax31-flash + hy4 + luna-r-high + deepseek4-flash", ("minimax31-flash", "hy4", "luna-r-high", "deepseek4-flash")),
                 ("haiku-xhigh + minimax31-flash + hy4 + luna-r-high", ("haiku-xhigh", "minimax31-flash", "hy4", "luna-r-high")), ("haiku-xhigh + sol + hy4 + minimax31-flash", ("haiku-xhigh", "sol", "hy4", "minimax31-flash"))):
    print(f"  fixed: known {len(set().union(*(known[c] for c in cb)))}/14  REAL {len(set().union(*(real[c] for c in cb)))}  findings/case {sum(nfind[c] for c in cb) / 10:.1f}  ${sum(COST[c] for c in cb):.2f}  {name}")
