"""Where the hits and false flags come from, for a titles-only entry: e1.py HARNESS_RESULTS_MODEL_DIR TOOL REVIEWER[,REVIEWER] [COMB].

Each judged issue is traced back to the finding whose title it came from (closest title on that PR), then split by reviewer,
severity and category. A golden comment is credited to the finding the judge picked as its best match, so per-bucket hit
counts are lower bounds.
"""
import collections, difflib, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
model_dir, tool, reviewers = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
comb = sys.argv[4] if len(sys.argv) > 4 else None
cases = json.load(open(HERE / "cases.json")); ev = json.load(open(model_dir / "evaluations.json"))
STRICT = {"bug", "security", "concurrency", "data", "api"}
rows = []  # one per judged issue: (url, reviewer, severity, category, rank, golden or None)
goldens = collections.Counter(); unmapped = 0
for url, case in cases.items():
    r = ev.get(url, {}).get(tool)
    if not r or r.get("skipped"): continue
    findings = []
    for rv in reviewers:
        fs = json.load(open(HERE / "out" / f"{case['name']}-{rv}-1.json"))["findings"]
        kept = set(json.load(open(HERE / "comb" / comb / f"{case['name']}-{rv}-1.json"))["kept"]) if comb else None
        order = sorted((i for i, f in enumerate(fs) if str(f.get("severity", "")).upper() in ("CONCERN", "FAIL") and (kept is None or i in kept)),
                       key=lambda i: (str(fs[i]["severity"]).upper() != "FAIL", i))
        findings += [(rv, fs[i], rank) for rank, i in enumerate(order)]
    def trace(text):
        best = max(findings, key=lambda x: difflib.SequenceMatcher(None, text.lower(), x[1]["title"].lower()).ratio(), default=None)
        return best
    for g in r["true_positives"] + r["false_negatives"]:
        if g.get("category") in STRICT: goldens[url] += 1
    for tp in r["true_positives"]:
        b = trace(tp["matched_candidate"])
        if b is None: unmapped += 1; continue
        rows.append((url, b[0], str(b[1]["severity"]).upper(), str(b[1].get("category")), b[2], tp.get("category") in STRICT, True))
    for fp in r["false_positives"]:
        b = trace(fp["candidate"])
        if b is None: unmapped += 1; continue
        rows.append((url, b[0], str(b[1]["severity"]).upper(), str(b[1].get("category")), b[2], False, False))
total_gold = sum(goldens.values())
def show(title, key):
    print(f"\n{title}")
    buckets = collections.defaultdict(lambda: [0, 0, 0])
    for row in rows:
        b = buckets[key(row)]; b[0] += row[6] and row[5]; b[1] += row[6] and not row[5]; b[2] += not row[6]
    for k, (hit, other_hit, miss) in sorted(buckets.items(), key=lambda kv: -kv[1][0]):
        print(f"  {str(k):28} strict hits {hit:3}  other golden hits {other_hit:3}  false flags {miss:3}  share real {(hit + other_hit) / max(1, hit + other_hit + miss):.0%}")
print(f"{tool}: {len(rows)} judged issues traced, {unmapped} untraced; strict golden comments {total_gold}")
show("by reviewer", lambda r: r[1]); show("by severity", lambda r: (r[1], r[2])); show("by finding category", lambda r: r[3])
print("\nkeep only each reviewer's first k findings per PR (FAIL first): strict recall (lower bound) and share real")
for k in (1, 2, 3, 4, 5, 99):
    sub = [r for r in rows if r[4] < k]; hit = sum(1 for r in sub if r[6] and r[5]); real = sum(1 for r in sub if r[6])
    print(f"  k={k:<3} issues {len(sub):4}  strict recall {hit / total_gold:.0%}  share real {real / max(1, len(sub)):.0%}")
