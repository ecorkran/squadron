"""Grid 2 score across all runs: run 1 (grade/, 6 configs) plus runs 2-3 (grade2/, 4 configs).

Per config: flaws found per run (mean over its runs), flaws found by any of its runs, and
the same split by case kind. Only the 4 configs with 3 runs get the union column.
"""
import json, pathlib, statistics, collections

HERE = pathlib.Path(__file__).resolve().parent
KINDS = ["arch", "slice", "tasks"]
ALL_ALIASES = ["fable-medium", "opus-high", "haiku-xhigh", "opus-medium", "sonnet-high", "sonnet-medium"]
REPEATED = {"fable-medium", "opus-high", "haiku-xhigh", "opus-medium"}

# (case, fid) -> {"kind": ..., "hits": {(alias, run)}}
flaws: dict[tuple[str, str], dict] = {}
for grade_dir, map_file in (("grade", "grade/map.json"), ("grade2", "grade2/map.json")):
    mapping = json.load(open(HERE / map_file))
    for case_dir in sorted((HERE / grade_dir).iterdir()):
        if not (case_dir / "flaws.json").exists():
            continue
        cid = case_dir.name
        kind = json.load(open(case_dir / "flaws.json"))["kind"]
        hits_path = case_dir / "hits.json"
        if not hits_path.exists():
            print("ungraded:", grade_dir, cid)
            continue
        by_id = {f["id"]: f for f in json.load(open(hits_path))["flaws"]}
        for f in json.load(open(case_dir / "flaws.json"))["flaws"]:
            entry = flaws.setdefault((cid, f["id"]), {"kind": kind, "hits": set()})
            for rid in by_id.get(f["id"], {}).get("hits", {}):
                m = mapping[f"{cid}/{rid}"]
                entry["hits"].add((m["alias"], m["run"]))


def report(title: str, keys: list) -> None:
    print(f"\n{title}: {len(keys)} flaws; found by any config/run: {sum(1 for k in keys if flaws[k]['hits'])}")
    print(f"{'config':14} {'mean/run':>9} {'recall/run':>10} {'union':>6} {'union%':>7}")
    for alias in ALL_ALIASES:
        runs = (1, 2, 3) if alias in REPEATED else (1,)
        per_run = [sum(1 for k in keys if (alias, r) in flaws[k]["hits"]) for r in runs]
        union = sum(1 for k in keys if any((alias, r) in flaws[k]["hits"] for r in runs))
        mean = statistics.mean(per_run)
        spread = f"{min(per_run)}-{max(per_run)}" if len(per_run) > 1 else "-"
        print(f"{alias:14} {mean:9.1f} {mean / len(keys):10.0%} {union:6} {union / len(keys):7.0%}  runs {spread}")


report("ALL", list(flaws))
for kind in KINDS:
    report(kind.upper(), [k for k, v in flaws.items() if v["kind"] == kind])

# Pairs and the four-config union, across all runs
def union_of(aliases: set[str]) -> int:
    return sum(1 for v in flaws.values() if any(a in aliases for a, _ in v["hits"]))

print("\nunion across all runs of a config set (of", len(flaws), "flaws):")
for combo in ({"fable-medium", "opus-high"}, {"fable-medium", "haiku-xhigh"}, {"opus-high", "haiku-xhigh"},
              REPEATED, set(ALL_ALIASES)):
    print(f"  {'+'.join(sorted(combo)):60} {union_of(combo)}")
print("found by none:", sum(1 for v in flaws.values() if not v["hits"]))
