import json, glob, collections, statistics
mp = json.load(open("map.json"))
CASE_ORDER = ["420-design","421-design","422-design","423-design","425-design","426-design","426-tasks","915-design","302-design"]
ALIASES = ["haiku-xhigh","opus-high","opus-medium","fable-medium","sonnet-high","sonnet-medium"]
flaws = {}                 # (case, fid) -> set of (alias, run) that hit it
total = collections.Counter()
for c in CASE_ORDER:
    try: d = json.load(open(f"{c}/hits.json"))
    except FileNotFoundError: continue
    for f in d["flaws"]:
        key = (c, f["id"]); flaws[key] = set()
        for rid in f["hits"]:
            m = mp[f"{c}/{rid}"]; flaws[key].add((m["alias"], m["run"]))
print("cases graded:", len({k[0] for k in flaws}), "flaws:", len(flaws))
print(f"{'model':14} {'run1':>5} {'run2':>5} {'run3':>5} {'mean/run':>8} {'union3':>7} {'any-run hits':>12}")
for a in ALIASES:
    per = [sum(1 for k,v in flaws.items() if (a,r) in v) for r in (1,2,3)]
    union = sum(1 for k,v in flaws.items() if any((a,r) in v for r in (1,2,3)))
    print(f"{a:14} {per[0]:5} {per[1]:5} {per[2]:5} {statistics.mean(per):8.1f} {union:7} {union/len(flaws):12.0%}")
found_by_any = sum(1 for v in flaws.values() if v)
print("flaws found by any model/run:", found_by_any, "of", len(flaws))
# flaws found only by one model
solo = collections.Counter()
for k,v in flaws.items():
    models = {a for a,_ in v}
    if len(models)==1: solo[next(iter(models))] += 1
print("found by exactly one model:", dict(solo))
for k,v in flaws.items():
    print(k, sorted({a for a,_ in v}) if v else "-", len(v))
