"""Design reviews: 4-reviewer set vs repeats, location dedupe, vote filter, opus comb. Stored data only."""
import json, re, collections, statistics as st, pathlib, itertools
M = pathlib.Path("/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined")
F = json.load(open("flaws2.json")); MAT = {k for k, f in F.items() if f["sev"] == "unmarked"}
KIND = {k.split("/")[0]: f["kind"] for k, f in F.items()}
def loc(s):
    m = re.search(r"([^/\s:]+\.\w+):(\d+)(?:\s*-\s*(\d+))?", str(s or ""))
    return (m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))) if m else None
find = collections.defaultdict(list)  # (alias, run) -> findings
seen = set()
for g in ["grade", "grade2", "grade3", "grade4", "grade5"]:
    mapping = json.load(open(M / g / "map.json"))
    for cdir in sorted((M / g).iterdir()):
        if not (cdir / "hits.json").exists(): continue
        cid = cdir.name; hits = json.load(open(cdir / "hits.json"))["flaws"]
        for key, m in mapping.items():
            c, rid = key.split("/")
            if c != cid or (cid, m["alias"], m["run"]) in seen or not (cdir / f"{rid}.json").exists(): continue
            seen.add((cid, m["alias"], m["run"]))
            for x in json.load(open(cdir / f"{rid}.json"))["findings"]:
                fl = {f"{cid}/{h['id']}" for h in hits if x["i"] in h.get("hits", {}).get(rid, [])}
                find[(m["alias"], m["run"])].append(dict(case=cid, who=(m["alias"], m["run"]), i=x["i"], sev=x["severity"].upper(), loc=loc(x.get("location")), flaws=fl))
json.dump({f"{a}#{r}": v for (a, r), v in find.items()}, open("design_findings.json", "w"), default=list)

def cluster(fs, gap):
    """Union findings in one case that cite the same file within `gap` lines of each other."""
    parent = list(range(len(fs)))
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i, j in itertools.combinations(range(len(fs)), 2):
        a, b = fs[i]["loc"], fs[j]["loc"]
        if a and b and a[0] == b[0] and a[1] <= b[2] + gap and b[1] <= a[2] + gap: parent[root(i)] = root(j)
    out = collections.defaultdict(list)
    for i in range(len(fs)): out[root(i)].append(fs[i])
    return list(out.values())

def report(name, members, gap=3):
    fs_all = [f for m in members for f in find[m] if f["sev"] in ("CONCERN", "FAIL")]
    cases = sorted({f["case"] for m in members for f in find[m]})
    n_find = len(fs_all); n_real = sum(1 for f in fs_all if f["flaws"])
    raw_mat = set().union(*(f["flaws"] for f in fs_all)) & MAT
    clusters = [c for cid in cases for c in cluster([f for f in fs_all if f["case"] == cid], gap)]
    multi = [c for c in clusters if len({f["who"] for f in c}) >= 2]
    vote_mat = set().union(*(f["flaws"] for c in multi for f in c)) & MAT if multi else set()
    real_c = sum(1 for c in clusters if any(f["flaws"] for f in c)); real_m = sum(1 for c in multi if any(f["flaws"] for f in c))
    # dedupe quality on pairs with known truth
    same = diff = same_ok = diff_bad = 0
    for cid in cases:
        cl = cluster([f for f in fs_all if f["case"] == cid], gap); idx = {id(f): n for n, c in enumerate(cl) for f in c}
        keyed = [f for f in fs_all if f["case"] == cid and f["flaws"]]
        for a, b in itertools.combinations(keyed, 2):
            if a["who"] == b["who"]: continue
            if a["flaws"] & b["flaws"]: same += 1; same_ok += idx[id(a)] == idx[id(b)]
            else: diff += 1; diff_bad += idx[id(a)] == idx[id(b)]
    nd = len(cases)
    print(f"{name}\n  raw: {n_find / nd:.1f} findings/doc, {n_real / nd:.1f} hit the key ({n_real / n_find:.0%}); material flaws {len(raw_mat)}/39")
    print(f"  line-dedupe (gap {gap}): {len(clusters) / nd:.1f} items/doc ({1 - len(clusters) / n_find:.0%} fewer), {real_c / len(clusters):.0%} hit the key; same-flaw pairs merged {same_ok}/{same}, different-flaw pairs wrongly merged {diff_bad}/{diff}")
    print(f"  keep only items 2+ reviewers raised: {len(multi) / nd:.1f} items/doc, {real_m / max(1, len(multi)):.0%} hit the key; material flaws {len(vote_mat)}/39")
    return fs_all
SET4 = [("haiku-xhigh", 1), ("minimax31-flash", 1), ("hy4", 1), ("mimo", 1)]
report("4 cheap (haiku-xhigh, minimax31-flash, hy4, mimo)", SET4)
report("haiku-xhigh x3", [("haiku-xhigh", r) for r in (1, 2, 3)])
report("haiku-xhigh x1", [("haiku-xhigh", 1)])
report("fable-medium x3", [("fable-medium", r) for r in (1, 2, 3)])
report("fable-medium + haiku-xhigh", [("fable-medium", 1), ("haiku-xhigh", 1)])
for gap in (0, 10, 25): report(f"4 cheap, gap {gap}", SET4, gap)

print("\nmaterial recall by document kind (flaws: arch/slice/tasks):", {k: sum(1 for x in MAT if F[x]["kind"] == k) for k in ("arch", "slice", "tasks")})
for name, members in (("4 cheap", SET4), ("haiku x3", [("haiku-xhigh", r) for r in (1, 2, 3)]), ("haiku x1", [("haiku-xhigh", 1)]), ("minimax31-flash", [("minimax31-flash", 1)]), ("hy4", [("hy4", 1)]), ("mimo", [("mimo", 1)]), ("fable-medium", [("fable-medium", 1)])):
    got = set().union(*(f["flaws"] for m in members for f in find[m])) & MAT
    print(f"  {name:18}", "  ".join(f"{k} {sum(1 for x in got if F[x]['kind'] == k)}/{sum(1 for x in MAT if F[x]['kind'] == k)}" for k in ("arch", "slice", "tasks")))

# opus-high comb on haiku-xhigh design reviews
print("\nopus-high comb on haiku-xhigh design reviews, by kind:")
tot = collections.defaultdict(collections.Counter); kept_mat = set(); raw_mat = set()
for (a, r), fs in find.items():
    if a != "haiku-xhigh": continue
    by_case = collections.defaultdict(list)
    for f in fs: by_case[f["case"]].append(f)
    for cid, cf in by_case.items():
        p = M / "comb" / "out" / "opus-high" / f"{cid}-haiku-xhigh-{r}.json"
        if not p.exists(): continue
        d = json.load(open(p)); keep = {d["refs"][fid] for fid, (dec, _) in d["decisions"].items() if dec == "KEEP"}; judged = set(d["refs"].values())
        for f in cf:
            if f["i"] not in judged: continue
            t = tot[KIND[cid]]; real = bool(f["flaws"]); k = f["i"] in keep
            t["real" if real else "noise"] += 1; t[("real" if real else "noise") + ("_kept" if k else "_drop")] += 1
            raw_mat |= f["flaws"] & MAT
            if k: kept_mat |= f["flaws"] & MAT
for k, t in tot.items():
    print(f"  {k:6} real kept {t['real_kept']}/{t['real']} ({t['real_kept'] / t['real']:.0%})  noise dropped {t['noise_drop']}/{t['noise']} ({t['noise_drop'] / t['noise']:.0%})  precision {t['real'] / (t['real'] + t['noise']):.0%} -> {t['real_kept'] / (t['real_kept'] + t['noise_kept']):.0%}")
print(f"  material flaws, any of 3 runs: raw {len(raw_mat)}/39, after comb {len(kept_mat)}/39")
