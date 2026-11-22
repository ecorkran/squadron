"""Dump one reviewer's credited hits on code-needing flaws (flaw text beside the finding credited) for a human or second-model read."""
import json, pathlib, sys
M = pathlib.Path(__file__).resolve().parent.parent / "20261116-mined"
alias, run, want = sys.argv[1], int(sys.argv[2]), sys.argv[3]
F = json.load(open("flaws2.json"))
def need(s):
    s = s.lower().strip()
    return "code" if s.startswith("code") or s.startswith("doc plus the regex") else "doc"
n = 0
for g in ["grade", "grade2", "grade3", "grade4", "grade5"]:
    mapping = json.load(open(M / g / "map.json"))
    for key, m in mapping.items():
        if m["alias"] != alias or m["run"] != run: continue
        cid, rid = key.split("/"); cdir = M / g / cid
        if not (cdir / "hits.json").exists(): continue
        fs = {x["i"]: x for x in json.load(open(cdir / f"{rid}.json"))["findings"]}
        for h in json.load(open(cdir / "hits.json"))["flaws"]:
            fk = f"{cid}/{h['id']}"
            if need(F[fk]["needs"]) != want or not h.get("hits", {}).get(rid): continue
            n += 1
            print(f"\n### {n}. {fk} [{F[fk]['sev']}]\nFLAW: {F[fk]['text'][:520]}")
            for i in h["hits"][rid]:
                x = fs[i]; print(f"FINDING ({x['severity']}) {x['title']}\n   {x['description'][:620]}")
