import json, glob, collections, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
mp = json.load(open(HERE / "map.json"))
ALIASES = ["haiku-xhigh", "opus-high", "opus-medium", "fable-medium", "sonnet-high", "sonnet-medium"]
KINDS = ["arch", "slice", "tasks"]
# (case, fid) -> (kind, set of aliases that hit it)
flaws = {}
missing = []
for d in sorted(p for p in HERE.iterdir() if (p / "flaws.json").exists()):
    cid = d.name
    fj = json.load(open(d / "flaws.json"))
    try:
        hits = json.load(open(d / "hits.json"))
    except FileNotFoundError:
        missing.append(cid); continue
    by_id = {f["id"]: f for f in hits["flaws"]}
    for f in fj["flaws"]:
        found = set()
        for rid in by_id.get(f["id"], {}).get("hits", {}):
            found.add(mp[f"{cid}/{rid}"]["alias"])
        flaws[(cid, f["id"])] = (fj["kind"], found)
if missing:
    print("ungraded cases:", missing)

def table(title, keys):
    n = len(keys)
    print(f"\n{title}: {n} flaws; found by any model: {sum(1 for k in keys if flaws[k][1])}")
    print(f"{'config':14} {'found':>6} {'recall':>7}")
    for a in ALIASES:
        c = sum(1 for k in keys if a in flaws[k][1])
        print(f"{a:14} {c:6} {c / n if n else 0:7.0%}")

table("ALL", list(flaws))
for kind in KINDS:
    table(kind.upper(), [k for k, v in flaws.items() if v[0] == kind])
solo = collections.Counter(next(iter(v[1])) for v in flaws.values() if len(v[1]) == 1)
print("\nfound by exactly one config:", dict(solo))
print("found by none:", sum(1 for v in flaws.values() if not v[1]))
