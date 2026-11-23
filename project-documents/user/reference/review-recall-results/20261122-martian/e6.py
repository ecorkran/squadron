"""Does agreement between truth-only verifiers separate real findings from the rest? e6.py HARNESS_MODEL_DIR

For each behavior-lane finding of haiku-xhigh: how many of the verifiers (comb/truth-<model>) kept it, against the judge's
verdict on the lane entry (sq-haiku-lane-t). A golden comment is credited to the judge's best-matching finding, so hit
counts are lower bounds. Nothing is dropped here; the tiers are labels.
"""
import collections, difflib, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
LANE = {"correctness", "security-hygiene", "error-handling-observability", "consistency-rot", "type-contract-debt"}
STRICT = {"bug", "security", "concurrency", "data", "api"}; HIGH = {"Critical", "High"}
VERIFIERS = ["opus-high", "sol-r", "fable-high"]
ev = json.load(open(pathlib.Path(sys.argv[1]) / "evaluations.json")); cases = json.load(open(HERE / "cases.json"))
tier = collections.defaultdict(collections.Counter); by_set = collections.defaultdict(collections.Counter); gold = collections.Counter()
for url, case in cases.items():
    r = ev[url]["sq-haiku-lane-t"]; fs = json.load(open(HERE / "out" / f"{case['name']}-haiku-xhigh-1.json"))["findings"]
    pool = [i for i, f in enumerate(fs) if str(f.get("severity", "")).upper() in ("CONCERN", "FAIL") and str(f.get("category")) in LANE]
    kept = {v: set(json.load(open(HERE / "comb" / f"truth-{v}" / f"{case['name']}-haiku-xhigh-1.json"))["kept"]) for v in VERIFIERS}
    trace = lambda text: max(pool, key=lambda i: difflib.SequenceMatcher(None, text.lower(), fs[i]["title"].lower()).ratio())
    label = {}
    for g in r["true_positives"] + r["false_negatives"]:
        if g.get("category") in STRICT: gold["strict"] += 1; gold["high"] += g["severity"] in HIGH
    for tp in r["true_positives"]:
        i = trace(tp["matched_candidate"]); kind = "strict_high" if tp.get("category") in STRICT and tp["severity"] in HIGH else "strict_low" if tp.get("category") in STRICT else "other_hit"
        label.setdefault(i, []).append(kind)
    for fp in r["false_positives"]: label.setdefault(trace(fp["candidate"]), []).append("false")
    for i in pool:
        votes = tuple(v for v in VERIFIERS if i in kept[v]); kinds = label.get(i, ["untraced"])
        for c in (tier[len(votes)], by_set[votes or ("none",)]):
            c["n"] += 1
            for k in kinds: c[k] += 1
def line(name, c):
    hits = c["strict_high"] + c["strict_low"]
    return f"{name:34}{c['n']:>5}{hits:>7}{c['strict_high']:>10}{c['other_hit']:>7}{c['false']:>7}{(hits + c['other_hit']) / max(1, hits + c['other_hit'] + c['false']):>9.0%}"
print(f"strict golden comments {gold['strict']}, critical+high {gold['high']}\n{'verifiers that kept it':34}{'n':>5}{'hits':>7}{'crit+high':>10}{'other':>7}{'false':>7}{'% real':>9}")
for k in (3, 2, 1, 0): print(line(f"{k} of 3", tier[k]))
print("\nkeep a finding when at least k verifiers kept it:")
for k in (0, 1, 2, 3):
    c = collections.Counter()
    for j in range(k, 4): c.update(tier[j])
    hits = c["strict_high"] + c["strict_low"]
    print(f"  k>={k}: findings {c['n']:4}  strict recall {hits / gold['strict']:.1%}  critical+high {c['strict_high']}/{gold['high']}  precision {hits / max(1, hits + c['false']):.1%}  false flags {c['false']}")
print("\nby exact set:"); [print(line(" + ".join(s), c)) for s, c in sorted(by_set.items(), key=lambda kv: -kv[1]["n"])]
