"""Score the reading run: score.py PILE_DIR.

Reads each pile's hits.json (blind grades), this folder's map.json and the flaw tags in the key
(what finding a flaw needs, and whether it is tagged minor). Prints, per reviewer, the stored
review (squadron 0.24.31) beside the new ones (current templates): flaws found by what they need,
material flaws found, tool calls and findings. Then the flaws gained and lost between the stored
run and new run 1, and how the stored reviews' new grades compare with their 2026-11-16 grades.
"""
import collections, json, pathlib, re, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent / "20261116-mined"
piles = pathlib.Path(sys.argv[1])
mapping = json.load(open(HERE / "map.json"))
ALIASES = ["haiku-xhigh", "sonnet-high", "opus-high", "fable-high"]


def need(text: str) -> str:
    """What finding the flaw needs, from the key's `Needs:` note (the 20261122-recut rule)."""
    found = re.search(r"Needs:\s*(.*)$", text, re.S)
    note = found.group(1).strip().lower() if found else ""
    if note.startswith("code") or note.startswith("doc plus the regex"):
        return "code"
    if note.startswith("doc alone") or note.startswith("document alone"):
        return "doc"
    return "doc+doc"


def material(text: str) -> bool:
    """Not tagged minor or coverage: `**VALID**` with no parenthesis after it."""
    found = re.search(r"\*\*VALID\*\*\s*(\(([^)]*)\))?", text)
    return bool(found) and not found.group(2)


flaws = {}  # (case, flaw id) -> tags
found_by = collections.defaultdict(set)  # (arm, alias, run) -> {(case, flaw id)}
ungraded = []
for pile in sorted(p for p in piles.iterdir() if p.is_dir()):
    for flaw in json.load(open(pile / "flaws.json"))["flaws"]:
        flaws[(pile.name, flaw["id"])] = {"need": need(flaw["text"]), "material": material(flaw["text"])}
    if not (pile / "hits.json").exists():
        ungraded.append(pile.name)
        continue
    for flaw in json.load(open(pile / "hits.json"))["flaws"]:
        for rid, indexes in flaw["hits"].items():
            who = mapping[f"{pile.name}/{rid}"]
            key = (who["arm"], who["alias"], who["run"])
            found_by[key]  # a review with no hits still has a row
            if indexes:
                found_by[key].add((pile.name, flaw["id"]))
if ungraded:
    print(f"NOT GRADED ({len(ungraded)}): {' '.join(ungraded)}")
graded = {key for key in flaws if key[0] not in ungraded}
totals = collections.Counter(flaws[key]["need"] for key in graded)
n_material = sum(flaws[key]["material"] for key in graded)
print(f"{len(graded)} flaws graded: {dict(totals)}, {n_material} material\n")


def effort(arm: str, alias: str, run: int) -> tuple[float, float]:
    folder = HERE / "out" if arm == "new" else MINED / "out"
    records = [json.load(open(path)) for path in folder.glob(f"*-{alias}-{run}.json")]
    calls = statistics.median(r.get("tool_calls_made") or 0 for r in records)
    raised = statistics.median(sum(1 for f in r["findings"] if f["severity"] != "PASS") for r in records)
    return calls, raised


print(f"{'reviewer':13}{'arm':8}{'run':>4}{'code':>10}{'doc':>10}{'doc+doc':>10}{'all':>10}{'material':>10}{'calls':>7}{'findings':>9}")
for alias in ALIASES:
    for arm, run in (("stored", 1), ("new", 1), ("new", 2)):
        key = (arm, alias, run)
        if key not in found_by:
            continue
        hit = found_by[key] & graded
        cells = [f"{sum(1 for k in hit if flaws[k]['need'] == kind)}/{totals[kind]}" for kind in ("code", "doc", "doc+doc")]
        calls, raised = effort(arm, alias, run)
        print(f"{alias:13}{arm:8}{run:>4}{cells[0]:>10}{cells[1]:>10}{cells[2]:>10}{f'{len(hit)}/{len(graded)}':>10}"
              f"{f'{sum(flaws[k]['material'] for k in hit)}/{n_material}':>10}{calls:>7.0f}{raised:>9.0f}")
    print()

print("flaws gained and lost, stored run 1 -> new run 1")
for alias in ALIASES:
    old, new = found_by[("stored", alias, 1)] & graded, found_by[("new", alias, 1)] & graded
    by_need = lambda keys: dict(collections.Counter(flaws[k]["need"] for k in keys))
    print(f"  {alias:13} kept {len(old & new):3}  gained {len(new - old):3} {by_need(new - old)}  lost {len(old - new):3} {by_need(old - new)}")

print("\nstored reviews: this grading against the 2026-11-16 grading of the same review")
earlier = {}  # (case, alias) -> flaw ids hit, run 1, first grading wins (as 20261122-recut/build.py)
for grade in ("grade", "grade2", "grade3", "grade4", "grade5"):
    old_map = json.load(open(MINED / grade / "map.json"))
    for key, who in old_map.items():
        case, rid = key.split("/")
        hits_path = MINED / grade / case / "hits.json"
        if who["run"] != 1 or who["alias"] not in ALIASES or (case, who["alias"]) in earlier or not hits_path.exists():
            continue
        earlier[(case, who["alias"])] = {f["id"] for f in json.load(open(hits_path))["flaws"] if f["hits"].get(rid)}
for alias in ALIASES:
    now = found_by[("stored", alias, 1)] & graded
    then = {(case, fid) for (case, a), ids in earlier.items() if a == alias and case not in ungraded for fid in ids}
    print(f"  {alias:13} then {len(then):3}  now {len(now):3}  both {len(then & now):3}  only then {len(then - now):3}  only now {len(now - then):3}")
