import json, collections, statistics as st, itertools, random
R = json.load(open("reviews.json")); F = json.load(open("flaws2.json"))
def need(s):
    s = s.lower().strip()
    if s.startswith("code") or s.startswith("doc plus the regex"): return "code"
    if s.startswith("doc alone") or s.startswith("document alone"): return "doc"
    return "doc+doc"
for f in F.values(): f["need"] = need(f["needs"]); f["material"] = f["sev"] == "unmarked"
print("material by need:", collections.Counter((f["material"], f["need"]) for f in F.values()))
hit = collections.defaultdict(set)   # (alias, run) -> set of flaw keys
cost = collections.defaultdict(list); cases = collections.defaultdict(set); finds = collections.defaultdict(list)
for r in R:
    k = (r["alias"], r["run"]); cases[k].add(r["case"]); finds[k].append(r["nfind"])
    if r["cost"] is not None: cost[k].append(r["cost"])
    hit[k] |= {f"{r['case']}/{fid}" for fid in r["hit"]}
full = [k for k in hit if len(cases[k]) == 43]
ALL = set(F); MAT = {k for k, f in F.items() if f["material"]}
c = lambda k: st.mean(cost[k]) if cost[k] else float("nan")
print(f"\n{'member':20}{'all/82':>7}{'mat/39':>7}{'mat doc':>8}{'mat d+d':>8}{'mat code':>9}{'finds':>6}{'$/rev':>7}")
sub = lambda S, n: {k for k in S if F[k]["need"] == n}
for k in sorted(full, key=lambda k: -len(hit[k] & MAT)):
    print(f"{k[0] + ' #' + str(k[1]):20}{len(hit[k]):>7}{len(hit[k] & MAT):>7}{len(hit[k] & sub(MAT, 'doc')):>5}/{len(sub(MAT, 'doc')):<2}{len(hit[k] & sub(MAT, 'doc+doc')):>5}/{len(sub(MAT, 'doc+doc')):<2}{len(hit[k] & sub(MAT, 'code')):>6}/{len(sub(MAT, 'code')):<2}{st.mean(finds[k]):>6.1f}{c(k):>7.2f}")
anyone = set().union(*hit.values())
print("\nmaterial flaws found by any review at all:", len(anyone & MAT), "of", len(MAT), "| all:", len(anyone), "of 82")

def best(pool, n, target):
    out = []
    for combo in itertools.combinations(pool, n):
        u = set().union(*(hit[k] for k in combo)) & target
        out.append((len(u), -sum(c(k) for k in combo), combo))
    return sorted(out, reverse=True)[:4]
cheap = [k for k in full if c(k) < 0.30]
print("\nbest unions, cheap members only (< $0.30 a review), material flaws of 39:")
for n in (2, 3, 4, 5):
    for u, negc, combo in best(cheap, n, MAT)[:2]:
        print(f"  {n}: {u}/39 = {u / 39:.0%}  ${-negc:.2f}  all-flaw union {len(set().union(*(hit[k] for k in combo)))}/82  " + ", ".join(f"{a}#{r}" for a, r in combo))
print("haiku-xhigh x3:", len((hit[('haiku-xhigh', 1)] | hit[('haiku-xhigh', 2)] | hit[('haiku-xhigh', 3)]) & MAT), "/39")
print("fable-medium#1 + haiku-xhigh#1:", len((hit[('fable-medium', 1)] | hit[('haiku-xhigh', 1)]) & MAT), "/39")

# honest check: choose the best cheap triple on half the cases, score it on the other half
random.seed(7); caselist = sorted({k.split('/')[0] for k in F}); res = []; picks = collections.Counter()
for _ in range(300):
    random.shuffle(caselist); tr = set(caselist[:21]); 
    trM = {k for k in MAT if k.split('/')[0] in tr}; teM = MAT - trM
    u, negc, combo = best(cheap, 3, trM)[0]
    res.append(len(set().union(*(hit[k] for k in combo)) & teM) / len(teM)); picks[tuple(sorted(a for a, _ in combo))] += 1
print(f"\nheld-out recall of the triple picked on the other half (300 splits): mean {st.mean(res):.0%}, 10th pct {sorted(res)[30]:.0%}, 90th pct {sorted(res)[270]:.0%}")
print("most-picked triples:", picks.most_common(4))
