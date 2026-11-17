"""cheap OpenRouter reviewers vs the anchors graded beside them (haiku-xhigh run 1, fable-medium run 1), from grade4/."""
import json, pathlib, collections
HERE = pathlib.Path(__file__).resolve().parent / "grade4"
mapping = json.load(open(HERE / "map.json"))
found = collections.defaultdict(lambda: collections.Counter())
total = collections.Counter()
for case_dir in sorted(p for p in HERE.iterdir() if (p / "flaws.json").exists()):
    flaws = json.load(open(case_dir / "flaws.json"))
    kind = flaws["kind"]
    hits = {f["id"]: f for f in json.load(open(case_dir / "hits.json"))["flaws"]}
    total[kind] += len(flaws["flaws"])
    for f in flaws["flaws"]:
        for rid, found_in in hits.get(f["id"], {}).get("hits", {}).items():
            if not found_in: continue
            found[mapping[f"{case_dir.name}/{rid}"]["alias"]][kind] += 1
print(f"{'config':14} {'all':>5} " + " ".join(f"{k:>6}" for k in sorted(total)) + f"   of {sum(total.values())}")
for alias, c in sorted(found.items(), key=lambda kv: -sum(kv[1].values())):
    print(f"{alias:14} {sum(c.values()):5} " + " ".join(f"{c[k]:6}" for k in sorted(total)))
