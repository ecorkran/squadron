"""The reading run by document kind, and what the reviews that read little found: by_kind.py PILE_DIR.

Reads the same files as score.py. Prints, per document kind (arch, slice, tasks) and reviewer,
the flaws found by the stored review and by the new ones; the reviews where no model ran (the
task gate imposed the verdict); the new reviews grouped by tool calls made against the share of
their case's flaws they found; and the unions of new run-1 reviews over the flaws a model saw.
"""
import collections, json, pathlib, re, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent / "20261116-mined"
piles = pathlib.Path(sys.argv[1])
mapping = json.load(open(HERE / "map.json"))
ALIASES = ["haiku-xhigh", "sonnet-high", "opus-high", "fable-high"]
KINDS = ["arch", "slice", "tasks"]
GATE_MODEL = "squadron-task-gate"  # the record's `model` when the task gate imposed the verdict
CALL_BANDS = [(0, 3), (4, 10), (11, 25), (26, None)]
COST = {"haiku-xhigh": 0.33, "sonnet-high": 0.45, "opus-high": 1.25, "fable-high": 3.06}  # README table


def needs_code(text: str) -> bool:
    """The key's `Needs:` note starts with code (score.py's rule)."""
    found = re.search(r"Needs:\s*(.*)$", text, re.S)
    note = found.group(1).strip().lower() if found else ""
    return note.startswith("code") or note.startswith("doc plus the regex")


def record(case: str, arm: str, alias: str, run: int) -> dict:
    folder = HERE / "out" if arm == "new" else MINED / "out"
    return json.load(open(folder / f"{case}-{alias}-{run}.json"))


def raised(rec: dict) -> int:
    return sum(1 for finding in rec["findings"] if finding["severity"] != "PASS")


kind_of, flaws = {}, {}  # case -> kind; (case, flaw id) -> needs the code
hits = collections.defaultdict(set)  # (case, arm, alias, run) -> flaw ids found
for pile in sorted(p for p in piles.iterdir() if p.is_dir()):
    key = json.load(open(pile / "flaws.json"))
    kind_of[pile.name] = key["kind"]
    for flaw in key["flaws"]:
        flaws[(pile.name, flaw["id"])] = needs_code(flaw["text"])
    for flaw in json.load(open(pile / "hits.json"))["flaws"]:
        for rid, indexes in flaw["hits"].items():
            who = mapping[f"{pile.name}/{rid}"]
            review = (pile.name, who["arm"], who["alias"], who["run"])
            hits[review]  # a review with no hits still has a row
            if indexes:
                hits[review].add(flaw["id"])
records = {review: record(*review) for review in hits}
in_case = collections.Counter(case for case, _ in flaws)

print("found by kind: stored run 1 -> new runs; flaws found (flaws needing the code found), median tool calls")
for kind in KINDS:
    total = [k for k in flaws if kind_of[k[0]] == kind]
    print(f" {kind}: {len(total)} flaws, {sum(flaws[k] for k in total)} need the code")
    for alias in ALIASES:
        cells = []
        for arm, run in (("stored", 1), ("new", 1), ("new", 2)):
            reviews = [r for r in hits if r[1:] == (arm, alias, run) and kind_of[r[0]] == kind]
            if not reviews:
                continue
            found = [(r[0], fid) for r in reviews for fid in hits[r]]
            calls = statistics.median(records[r].get("tool_calls_made") or 0 for r in reviews)
            cells.append(f"{arm} {run}: {len(found):2} ({sum(flaws[k] for k in found):2}) calls {calls:4.0f}")
        print(f"   {alias:12} " + "   ".join(cells))

gated = sorted(r for r in hits if records[r]["model"] == GATE_MODEL)
gated_cases = sorted({r[0] for r in gated if r[1] == "new"})
print(f"\nno model ran ({GATE_MODEL} imposed the verdict): {len(gated)} reviews")
for case in sorted({r[0] for r in gated}):
    arms = collections.Counter(r[1] for r in gated if r[0] == case)
    print(f"  {case}: {dict(arms)}, {in_case[case]} flaws, {sum(flaws[k] for k in flaws if k[0] == case)} need the code")

print("\nnew model reviews by tool calls made: reviews, flaws found of those in their cases, findings raised a review")
for kind in KINDS:
    print(f" {kind}")
    for low, high in CALL_BANDS:
        band = [r for r in hits if r[1] == "new" and kind_of[r[0]] == kind and records[r]["model"] != GATE_MODEL
                and low <= (records[r].get("tool_calls_made") or 0) and (high is None or (records[r].get("tool_calls_made") or 0) <= high)]
        if not band:
            continue
        got, available = sum(len(hits[r]) for r in band), sum(in_case[r[0]] for r in band)
        who = dict(collections.Counter(r[2] for r in band))
        label = f"{low}+" if high is None else f"{low}-{high}"
        print(f"   {label:6} {len(band):3} reviews  {got:3}/{available:3} = {got / available:4.0%}  raised {statistics.mean(raised(records[r]) for r in band):4.1f}  {who}")

live = {k for k in flaws if k[0] not in gated_cases}
print(f"\nunions of new run-1 reviews over the {len(live)} flaws a model saw ({sum(flaws[k] for k in live)} need the code); cost is the reviews' sum")
found_new = {(alias, run): {(r[0], fid) for r in hits if r[1:] == ("new", alias, run) for fid in hits[r]} & live
             for alias in ALIASES for run in (1, 2)}
SETS = [[("haiku-xhigh", 1)], [("sonnet-high", 1)], [("opus-high", 1)], [("fable-high", 1)],
        [("haiku-xhigh", 1), ("haiku-xhigh", 2)], [("haiku-xhigh", 1), ("sonnet-high", 1)], [("haiku-xhigh", 1), ("opus-high", 1)],
        [("haiku-xhigh", 1), ("fable-high", 1)], [("haiku-xhigh", 1), ("sonnet-high", 1), ("opus-high", 1), ("fable-high", 1)]]
for members in SETS:
    union = set().union(*(found_new[m] for m in members))
    name = " + ".join(f"{alias} {run}" for alias, run in members)
    print(f"  {name:58} {len(union):2}/{len(live)}  code {sum(flaws[k] for k in union):2}  ${sum(COST[alias] for alias, _ in members):.2f}")
