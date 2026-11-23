"""Strict-profile recall by golden severity, squadron entries beside the harness's tools (same judge model). e3.py HARNESS_RESULTS_DIR"""
import collections, json, pathlib, sys
res = pathlib.Path(sys.argv[1]); STRICT = {"bug", "security", "concurrency", "data", "api"}
ours = json.load(open(res / "anthropic_claude-sonnet-4.5" / "evaluations.json")); theirs = json.load(open(res / "anthropic_claude-sonnet-4-5-20250929" / "evaluations.json"))
def table(ev, tools):
    out = {}
    for t in tools:
        hit = collections.Counter(); tot = collections.Counter(); fp = 0; n = 0
        for url, by in ev.items():
            r = by.get(t)
            if not r or r.get("skipped"): continue
            n += 1; fp += len(r["false_positives"])
            for g in r["true_positives"]:
                if g.get("category") in STRICT: hit[g["severity"]] += 1; tot[g["severity"]] += 1
            for g in r["false_negatives"]:
                if g.get("category") in STRICT: tot[g["severity"]] += 1
        out[t] = (hit, tot, fp, n)
    return out
ours_tools = sorted({t for by in ours.values() for t in by if t.endswith("-t")})  # every titles-only squadron entry judged so far
rows = {**table(ours, ours_tools), **table(theirs, ["augment", "qodo-extended-v2", "cubic-v2", "copilot-v2", "coderabbit", "greptile-v4-1", "bugbot", "claude-code", "devin"])}
print(f"{'entry':18}{'Critical':>10}{'High':>10}{'Crit+High':>11}{'Medium':>10}{'Low':>9}{'false flags':>13}{'PRs':>5}")
for t, (hit, tot, fp, n) in rows.items():
    ch = hit["Critical"] + hit["High"]; cht = tot["Critical"] + tot["High"]
    cell = lambda s: f"{hit[s]}/{tot[s]}"
    print(f"{t:18}{cell('Critical'):>10}{cell('High'):>10}{f'{ch}/{cht} {ch / max(1, cht):.0%}':>11}{cell('Medium'):>10}{cell('Low'):>9}{fp:>13}{n:>5}")
h = {(u, g["golden_comment"]) for u, by in ours.items() if "sq-haiku-t" in by for g in by["sq-haiku-t"]["true_positives"]}
s = {(u, g["golden_comment"]) for u, by in ours.items() if "sq-solr-t" in by for g in by["sq-solr-t"]["true_positives"]}
allg = {(u, g["golden_comment"]) for u, by in ours.items() if "sq-haiku-t" in by for g in by["sq-haiku-t"]["true_positives"] + by["sq-haiku-t"]["false_negatives"] if g.get("category") in STRICT}
print(f"\nsol-r alone finds {len((s & allg) - h)} of the {len(allg - h)} strict golden comments haiku-xhigh missed; haiku finds {len((h & allg) - s)} that sol-r missed")
