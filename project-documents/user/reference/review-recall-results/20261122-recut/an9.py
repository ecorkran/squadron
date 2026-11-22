import json, collections, statistics as st, itertools, random
R = json.load(open("reviews.json")); F = json.load(open("flaws2.json"))
MAT = {k for k, f in F.items() if f["sev"] == "unmarked"}
hit = collections.defaultdict(set); cost = collections.defaultdict(list); cases = collections.defaultdict(set); finds = collections.defaultdict(list)
for r in R:
    k = (r["alias"], r["run"]); cases[k].add(r["case"]); finds[k].append(r["nfind"])
    if r["cost"] is not None: cost[k].append(r["cost"])
    hit[k] |= {f"{r['case']}/{fid}" for fid in r["hit"]}
c = lambda k: st.mean(cost[k]) if cost[k] else 9
cheap = [k for k in hit if len(cases[k]) == 43 and c(k) < 0.30]
caselist = sorted({k.split('/')[0] for k in F})
for n in (1, 2, 3, 4, 5):
    random.seed(11); te_scores = []; tr_scores = []
    combos = list(itertools.combinations(cheap, n))
    for _ in range(120):
        random.shuffle(caselist); tr = set(caselist[:21])
        trM = {k for k in MAT if k.split('/')[0] in tr}; teM = MAT - trM
        bestc = max(combos, key=lambda cb: (len(set().union(*(hit[k] for k in cb)) & trM), -sum(c(k) for k in cb)))
        u = set().union(*(hit[k] for k in bestc))
        tr_scores.append(len(u & trM) / len(trM)); te_scores.append(len(u & teM) / len(teM))
    print(f"cheap set of {n}: picked-on half {st.mean(tr_scores):.0%}, other half {st.mean(te_scores):.0%} (10th-90th pct {sorted(te_scores)[12]:.0%}-{sorted(te_scores)[108]:.0%})")
fixed = [("haiku-xhigh", 1), ("minimax31-flash", 1), ("hy4", 1), ("mimo", 1)]
u = set().union(*(hit[k] for k in fixed))
print("fixed haiku-xhigh + minimax31-flash + hy4 + mimo: material", len(u & MAT), "/39, all", len(u), "/82, cost $%.2f" % sum(c(k) for k in fixed), "CONCERN/FAIL findings per doc %.0f" % sum(st.mean(finds[k]) for k in fixed))
for k in fixed: print("  ", k[0], "alone:", len(hit[k] & MAT), "/39")
