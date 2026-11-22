import json, re, collections, statistics as st, pathlib
M = pathlib.Path("/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined")
F = json.load(open("flaws.json"))
sev = collections.Counter()
for k, f in F.items():
    m = re.search(r"\*\*VALID\*\*\s*(\(([^)]*)\))?", f["text"])
    f["sev"] = (m.group(2) or "unmarked").split(",")[0].split(";")[0].strip().lower() if m else "no-valid-tag"
    sev[f["sev"]] += 1
print(sev.most_common())
json.dump(F, open("flaws2.json", "w"))

# severity the reviewer gave to the finding that hit, and FAIL/CONCERN precision (lower bound: key is incomplete)
agg = collections.defaultdict(lambda: collections.Counter())
seen = set()
for g in ["grade", "grade2", "grade3", "grade4", "grade5"]:
    mapping = json.load(open(M / g / "map.json"))
    for cdir in sorted((M / g).iterdir()):
        if not (cdir / "hits.json").exists(): continue
        cid = cdir.name
        hits = json.load(open(cdir / "hits.json"))["flaws"]
        for key, m in mapping.items():
            c, rid = key.split("/")
            if c != cid or (cid, m["alias"], m["run"]) in seen: continue
            seen.add((cid, m["alias"], m["run"]))
            rf = cdir / f"{rid}.json"
            if not rf.exists(): continue
            fs = {x["i"]: x["severity"].upper() for x in json.load(open(rf))["findings"]}
            hit_idx = {i for fl in hits for i in fl.get("hits", {}).get(rid, [])}
            a = agg[m["alias"]]
            for i, s in fs.items():
                a[s] += 1
                if i in hit_idx: a[s + "_hit"] += 1
print(f"\n{'config':16}{'FAIL':>6}{'hit':>5}{'prec':>6}{'CONCERN':>9}{'hit':>5}{'prec':>6}{'NOTE':>6}{'hit':>5}   share of hits labelled FAIL")
for a in ["fable-high", "fable-medium", "haiku-xhigh", "opus-high", "opus-medium", "sonnet-high", "sonnet-medium", "hy4", "minimax31-flash", "qwen38-flash", "glm-flash", "deepseek4-flash", "mimo"]:
    c = agg[a]; th = c["FAIL_hit"] + c["CONCERN_hit"] + c["NOTE_hit"]
    p = lambda k: f"{c[k + '_hit'] / c[k]:.0%}" if c[k] else "-"
    print(f"{a:16}{c['FAIL']:>6}{c['FAIL_hit']:>5}{p('FAIL'):>6}{c['CONCERN']:>9}{c['CONCERN_hit']:>5}{p('CONCERN'):>6}{c['NOTE']:>6}{c['NOTE_hit']:>5}   {c['FAIL_hit'] / th if th else 0:.0%}")
