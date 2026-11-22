"""Join every graded design review (mined set) with its recorded effort metrics."""
import json, pathlib, re, csv
M = pathlib.Path("/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined")
rows = {}   # (case, alias, run) -> row
flawinfo = {}  # (case, fid) -> {kind, needs, text}
for g in ["grade", "grade2", "grade3", "grade4", "grade5"]:
    mp = M / g / "map.json"
    if not mp.exists():
        print("no map", g); continue
    mapping = json.load(open(mp))
    for cdir in sorted((M / g).iterdir()):
        if not (cdir / "flaws.json").exists() or not (cdir / "hits.json").exists():
            continue
        cid = cdir.name
        fl = json.load(open(cdir / "flaws.json"))
        for f in fl["flaws"]:
            m = re.search(r"Needs:\s*(.*)$", f["text"], re.S)
            flawinfo[(cid, f["id"])] = {"kind": fl["kind"], "needs": (m.group(1).strip() if m else ""), "text": f["text"]}
        hits = {f["id"]: {rid for rid, v in f.get("hits", {}).items() if v} for f in json.load(open(cdir / "hits.json"))["flaws"]}
        for key, m in mapping.items():
            c, rid = key.split("/")
            if c != cid: continue
            k = (cid, m["alias"], m["run"])
            if k in rows: continue  # first grading wins (anchors are regraded later)
            rows[k] = {"case": cid, "alias": m["alias"], "run": m["run"], "kind": fl["kind"], "grade": g,
                       "nflaws": len(fl["flaws"]), "hit": sorted(fid for fid, rs in hits.items() if rid in rs)}
out = []
missing = 0
for (cid, alias, run), r in rows.items():
    p = M / "out" / f"{cid}-{alias}-{run}.json"
    if not p.exists():
        missing += 1; continue
    d = json.load(open(p))
    sev = [f.get("severity", "").upper() for f in d.get("findings", [])]
    r.update(tool_calls=d.get("tool_calls_made"), turns=d.get("turns"), prompt=d.get("prompt_tokens"),
             cached=d.get("cached_tokens"), completion=d.get("completion_tokens"), reasoning=d.get("reasoning_tokens"),
             reasoning_chars=d.get("reasoning_chars"), dur=d.get("duration_seconds"), cost=d.get("cost_usd"),
             verdict=d.get("verdict"), nfind=sum(1 for s in sev if s in ("CONCERN", "FAIL")), nfail=sev.count("FAIL"),
             nhit=len(r["hit"]))
    out.append(r)
print("reviews", len(out), "missing out json", missing, "flaws", len(flawinfo))
json.dump(out, open("reviews.json", "w")); json.dump({f"{c}/{f}": v for (c, f), v in flawinfo.items()}, open("flaws.json", "w"))
