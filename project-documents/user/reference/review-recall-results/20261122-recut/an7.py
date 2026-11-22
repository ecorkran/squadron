import json, re, collections, statistics as st, pathlib, subprocess, itertools, random
M = pathlib.Path("/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined")
F = json.load(open("flaws2.json"))
MAT = {k for k, f in F.items() if f["sev"] == "unmarked"}
# per (alias, run): flaws hit by a FAIL finding, by FAIL-or-CONCERN, by anything; and each hit's line position
lab = collections.defaultdict(lambda: collections.defaultdict(set)); seen = set()
flawline = collections.defaultdict(list)
for g in ["grade", "grade2", "grade3", "grade4", "grade5"]:
    mapping = json.load(open(M / g / "map.json"))
    for cdir in sorted((M / g).iterdir()):
        if not (cdir / "hits.json").exists(): continue
        cid = cdir.name; hits = json.load(open(cdir / "hits.json"))["flaws"]
        for key, m in mapping.items():
            c, rid = key.split("/")
            if c != cid or (cid, m["alias"], m["run"]) in seen: continue
            seen.add((cid, m["alias"], m["run"]))
            rf = cdir / f"{rid}.json"
            if not rf.exists(): continue
            fs = {x["i"]: x for x in json.load(open(rf))["findings"]}
            for fl in hits:
                for i in fl.get("hits", {}).get(rid, []):
                    if i not in fs: continue
                    s = fs[i]["severity"].upper(); fk = f"{cid}/{fl['id']}"
                    lab[(m["alias"], m["run"])][s].add(fk)
                    mm = re.search(r":(\d+)", str(fs[i].get("location", "")))
                    if mm: flawline[fk].append(int(mm.group(1)))
print("keys in graded finding:", list(fs[next(iter(fs))].keys()) if fs else None)
print(f"{'member':20}{'mat hit any label':>18}{'FAIL only':>10}{'FAIL+CONCERN':>13}")
for k in [("fable-high", 1), ("fable-medium", 1), ("haiku-xhigh", 1), ("opus-high", 1), ("sonnet-high", 1), ("minimax31-flash", 1), ("hy4", 1), ("glm-flash", 1), ("mimo", 1)]:
    d = lab[k]; anyl = (d["FAIL"] | d["CONCERN"] | d["NOTE"]) & MAT
    print(f"{k[0]:20}{len(anyl):>18}{len(d['FAIL'] & MAT):>10}{len((d['FAIL'] | d['CONCERN']) & MAT):>13}")
json.dump({k: v for k, v in flawline.items()}, open("flawline.json", "w"))
print("flaws with a line position from a hitting finding:", len(flawline))
