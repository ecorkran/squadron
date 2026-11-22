"""Estimate, from the judged haiku-xhigh titles entry, what a filter would score: e4.py HARNESS_MODEL_DIR [COMB_LABEL].

Each judged issue is traced to its finding; the filter is the behavior-lane categories, then (optionally) a comb's kept set.
Hit counts are lower bounds (a golden comment is credited only to the judge's best-matching finding).
"""
import collections, difflib, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
LANE = {"correctness", "security-hygiene", "error-handling-observability", "consistency-rot", "type-contract-debt"}
STRICT = {"bug", "security", "concurrency", "data", "api"}
ev = json.load(open(pathlib.Path(sys.argv[1]) / "evaluations.json")); comb = sys.argv[2] if len(sys.argv) > 2 else None
cases = json.load(open(HERE / "cases.json")); stats = collections.defaultdict(lambda: collections.Counter()); total = collections.Counter(); lost = []
for url, case in cases.items():
    r = ev[url]["sq-haiku-t"]; fs = json.load(open(HERE / "out" / f"{case['name']}-haiku-xhigh-1.json"))["findings"]
    pool = [i for i, f in enumerate(fs) if str(f.get("severity", "")).upper() in ("CONCERN", "FAIL")]
    kept = set(json.load(open(HERE / "comb" / comb / f"{case['name']}-haiku-xhigh-1.json"))["kept"]) if comb else None
    trace = lambda text: max(pool, key=lambda i: difflib.SequenceMatcher(None, text.lower(), fs[i]["title"].lower()).ratio())
    for g in r["true_positives"] + r["false_negatives"]:
        if g.get("category") in STRICT: total[g["severity"]] += 1
    for name, keep in (("all", lambda i: True), ("lane", lambda i: str(fs[i].get("category")) in LANE), ("lane+comb", lambda i: str(fs[i].get("category")) in LANE and (kept is None or i in kept))):
        for tp in r["true_positives"]:
            i = trace(tp["matched_candidate"])
            if tp.get("category") not in STRICT: continue
            if keep(i): stats[name][tp["severity"]] += 1; stats[name]["hit"] += 1
            elif name == "lane+comb" and str(fs[i].get("category")) in LANE: lost.append((case["name"], tp["severity"], fs[i]["title"]))
        stats[name]["false"] += sum(1 for fp in r["false_positives"] if keep(trace(fp["candidate"])))
gold = sum(total.values())
print(f"{'filter':12}{'recall':>8}{'precision':>10}{'hits':>6}{'false':>7}{'Critical':>10}{'High':>8}{'Medium':>8}{'Low':>6}")
for name, c in stats.items():
    print(f"{name:12}{c['hit'] / gold:>8.1%}{c['hit'] / max(1, c['hit'] + c['false']):>10.1%}{c['hit']:>6}{c['false']:>7}{str(c['Critical']) + '/' + str(total['Critical']):>10}{str(c['High']) + '/' + str(total['High']):>8}{str(c['Medium']) + '/' + str(total['Medium']):>8}{str(c['Low']) + '/' + str(total['Low']):>6}")
if comb:
    print(f"\nreal hits the comb dropped ({len(lost)}):")
    for name, sev, title in lost: print(f"  [{name} | golden {sev}] {title[:130]}")
