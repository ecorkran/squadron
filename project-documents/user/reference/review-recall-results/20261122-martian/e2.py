"""Two reads of the judged run. e2.py HARNESS_RESULTS_DIR
1. Real hits the opus-high comb dropped (after luna-r kept them), with the comb's stated reason.
2. Golden comments haiku-xhigh missed or found, against how many of the harness's listed tools found each.
"""
import collections, difflib, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
res = pathlib.Path(sys.argv[1]); ours = json.load(open(res / "anthropic_claude-sonnet-4.5" / "evaluations.json")); theirs = json.load(open(res / "anthropic_claude-sonnet-4-5-20250929" / "evaluations.json"))
cases = json.load(open(HERE / "cases.json")); STRICT = {"bug", "security", "concurrency", "data", "api"}
SHOWN = ["augment", "qodo-extended-v2", "cubic-v2", "copilot-v2", "coderabbit", "greptile-v4-1", "bugbot", "claude-code", "devin", "qodo-v2", "gemini-v2", "sourcery", "gitlab", "macroscope", "baz", "kodus-v2", "codeant-v2", "claude", "kg", "graphite", "gitar"]
print("== 1. real hits dropped by opus-high after luna-r kept them")
reasons = []; kept_hits = 0
for url, case in cases.items():
    r = ours.get(url, {}).get("sq-pair-luna-t")
    if not r: continue
    pool = []
    for rv in ("haiku-xhigh", "sol-r"):
        fs = json.load(open(HERE / "out" / f"{case['name']}-{rv}-1.json"))["findings"]
        luna = set(json.load(open(HERE / "comb" / "luna-r" / f"{case['name']}-{rv}-1.json"))["kept"])
        opus = json.load(open(HERE / "comb" / "luna-r+opus-high" / f"{case['name']}-{rv}-1.json"))
        back = {i: fid for fid, i in opus["refs"].items()}
        pool += [(rv, i, fs[i], opus["decisions"].get(back.get(i), ["?", ""])) for i in luna if str(fs[i].get("severity", "")).upper() in ("CONCERN", "FAIL")]
    for tp in r["true_positives"]:
        if tp.get("category") not in STRICT or not pool: continue
        rv, i, f, (verdict, why) = max(pool, key=lambda x: difflib.SequenceMatcher(None, tp["matched_candidate"].lower(), x[2]["title"].lower()).ratio())
        if verdict == "DROP": reasons.append((case["name"], rv, f["severity"], f["title"], tp["golden_comment"], tp.get("severity"), why))
        else: kept_hits += 1
print(f"strict hits in the luna-r entry: kept by opus {kept_hits}, dropped {len(reasons)}")
for name, rv, sev, title, gold, gsev, why in reasons:
    print(f"\n[{name} | {rv} {sev} | golden {gsev}] {title[:120]}\n   golden: {gold[:200]}\n   opus:   {why[:330]}")
print("\n== 2. golden comments (strict) and who finds them")
found_by = collections.defaultdict(set); info = {}
for url, tools in theirs.items():
    for t, r in tools.items():
        if t not in SHOWN or r.get("skipped"): continue
        for g in r["true_positives"]: found_by[(url, g["golden_comment"])].add(t)
        for g in r["true_positives"] + r["false_negatives"]: info[(url, g["golden_comment"])] = (g.get("severity"), g.get("category"))
h_hit = set(); h_all = set()
for url in cases:
    r = ours.get(url, {}).get("sq-haiku-t")
    if not r: continue
    for g in r["true_positives"]:
        if g.get("category") in STRICT: h_hit.add((url, g["golden_comment"])); h_all.add((url, g["golden_comment"]))
    for g in r["false_negatives"]:
        if g.get("category") in STRICT: h_all.add((url, g["golden_comment"]))
missed = h_all - h_hit
dist = lambda keys: collections.Counter(min(len(found_by.get(k, ())), 10) // 3 for k in keys)
lab = {0: "0-2 tools", 1: "3-5", 2: "6-8", 3: "9+"}
print("haiku-xhigh hit", len(h_hit), "missed", len(missed), "of", len(h_all))
print("  by how many of the 21 tools found it:   hit:", {lab[k]: v for k, v in sorted(dist(h_hit).items())}, "  missed:", {lab[k]: v for k, v in sorted(dist(missed).items())})
print("  missed by severity:", dict(collections.Counter(info.get(k, ("?",))[0] for k in missed)), " hit by severity:", dict(collections.Counter(info.get(k, ("?",))[0] for k in h_hit)))
print("  found by no listed tool at all:", sum(1 for k in h_all if not found_by.get(k)), "| of those haiku found:", sum(1 for k in h_hit if not found_by.get(k)))
print("  union of haiku-xhigh with one outside tool (strict recall):")
for t in ("augment", "qodo-extended-v2", "cubic-v2", "copilot-v2", "coderabbit", "bugbot", "greptile-v4-1"):
    theirs_hit = {k for k in h_all if t in found_by.get(k, ())}
    print(f"    {t:18} alone {len(theirs_hit) / len(h_all):.0%}  with haiku {len(theirs_hit | h_hit) / len(h_all):.0%}  haiku-only {len(h_hit - theirs_hit)}  tool-only {len(theirs_hit - h_hit)}")
print("\n  missed by haiku, found by 9+ tools:")
for k in sorted(missed, key=lambda k: -len(found_by.get(k, ()))):
    if len(found_by.get(k, ())) >= 9: print(f"   [{cases[k[0]]['name']} | {info[k][0]} {info[k][1]} | {len(found_by[k])} tools] {k[1][:230]}")
