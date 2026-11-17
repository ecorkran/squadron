"""Flaws found per reviewer from grade5/ (blind grades), with mean cost per review from out/.

Two tables: all 43 cases, and the 15-case subset where every reviewer ran. The subset table
includes the anchors scored on the same 15 cases, so its numbers are comparable down the column.
"""
import collections, glob, json, pathlib, statistics

HERE = pathlib.Path(__file__).resolve().parent
GRADE = HERE / "grade5"
mapping = json.load(open(GRADE / "map.json"))
cases = [line.split("\t")[0] for line in (HERE / "cases.tsv").read_text().splitlines()]
subset = set(cases[::3])
KINDS = ("arch", "slice", "tasks")


def review_cost(path: str) -> float | None:
    """First numeric cost_usd anywhere in a saved review, or None when the review has none."""
    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("cost_usd"), (int, float)):
                return node["cost_usd"]
            for value in node.values():
                found = walk(value)
                if found is not None:
                    return found
        return None
    return walk(json.load(open(path)))


found = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # scope -> alias -> kind
totals = collections.defaultdict(collections.Counter)  # scope -> kind
for case_dir in sorted(p for p in GRADE.iterdir() if (p / "flaws.json").exists()):
    hits_path = case_dir / "hits.json"
    assert hits_path.exists(), f"ungraded case {case_dir.name}"
    flaws = json.load(open(case_dir / "flaws.json"))
    kind = flaws["kind"]
    hits = {f["id"]: f for f in json.load(open(hits_path))["flaws"]}
    scopes = ["all"] + (["subset"] if case_dir.name in subset else [])
    for scope in scopes:
        totals[scope][kind] += len(flaws["flaws"])
    for flaw in flaws["flaws"]:
        for rid, hit_findings in hits.get(flaw["id"], {}).get("hits", {}).items():
            if not hit_findings:
                continue
            alias = mapping[f"{case_dir.name}/{rid}"]["alias"]
            for scope in scopes:
                found[scope][alias][kind] += 1


def mean_cost(alias: str) -> str:
    costs = [c for f in glob.glob(str(HERE / "out" / f"*-{alias}-1.json"))
             if (c := review_cost(f)) is not None]
    return f"${statistics.mean(costs):.3f}" if costs else "n/a"


for scope in ("all", "subset"):
    total = sum(totals[scope].values())
    print(f"\n== {scope}: {total} flaws ==  " + "  ".join(f"{k} {totals[scope][k]}" for k in KINDS))
    print(f"{'config':16} {'found':>5} " + " ".join(f"{k:>6}" for k in KINDS) + "   $/review")
    rows = sorted(found[scope].items(), key=lambda kv: -sum(kv[1].values()))
    for alias, counter in rows:
        print(f"{alias:16} {sum(counter.values()):5} " + " ".join(f"{counter[k]:6}" for k in KINDS)
              + f"   {mean_cost(alias)}")
