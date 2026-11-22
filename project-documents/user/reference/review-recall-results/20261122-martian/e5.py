"""Greptile's own benchmark, scored from the Code Review Bench run: e5.py HARNESS_OFFLINE_DIR TOOL [TOOL...]

Greptile lists one known bug per PR (greptile_cases.psv, from greptile.com/benchmarks.md). Each is matched to the golden comment
on the same PR with the closest wording; a tool "catches" the bug when the judge matched one of its issues to that golden comment.
Prints every pairing so a weak match can be seen and corrected by hand.
"""
import csv, difflib, json, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent; H = pathlib.Path(sys.argv[1]); tools = sys.argv[2:]
rows = list(csv.DictReader(open(HERE / "greptile_cases.psv"), delimiter="|"))
data = json.load(open(H / "results" / "benchmark_data.upstream.json")); ev = json.load(open(H / "results" / "anthropic_claude-sonnet-4.5" / "evaluations.json"))
norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
def score(a, b):
    wa, wb = set(norm(a)), set(norm(b)); return len(wa & wb) / max(1, len(wa)) + difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() / 4
by_title = {}
for url, v in data.items(): by_title.setdefault(v["pr_title"].strip().lower(), url)
caught = {t: 0 for t in tools}; table = []
for r in rows:
    url = by_title.get(r["pr_title"].strip().lower()) or max(data, key=lambda u: difflib.SequenceMatcher(None, r["pr_title"].lower(), data[u]["pr_title"].lower()).ratio())
    gold = max(data[url]["golden_comments"], key=lambda g: score(r["bug_summary"], g["comment"]))
    s = score(r["bug_summary"], gold["comment"]); hit = {}
    for t in tools:
        e = ev.get(url, {}).get(t, {}); hit[t] = any(tp["golden_comment"] == gold["comment"] for tp in e.get("true_positives", [])); caught[t] += hit[t]
    table.append((r, url, gold, s, hit))
for r, url, gold, s, hit in table:
    print(f"{r['repo'][:5]:5} {r['row']:>2} {r['severity'][:4]:4} match {s:.2f} " + " ".join("Y" if hit[t] else "." for t in tools) + f" | {r['bug_summary'][:62]:62} | {gold['comment'][:95]}")
print("\ncatch rate of 50:", {t: f"{caught[t]} ({caught[t] / 50:.0%})" for t in tools})
print("Greptile's page, same 50:", {k: sum(int(r[k]) for r in rows) for k in ("greptile", "copilot", "coderabbit", "bugbot", "graphite")})
