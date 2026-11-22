import json, re, collections, statistics as st, pathlib, subprocess
M = pathlib.Path("/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-results/20261116-mined")
REPOS = {"squadron": "/Users/manta/source/repos/manta/squadron", "context-forge": "/Users/manta/source/repos/manta/context-forge", "migratory": "/Users/manta/source/repos/manta/migratory"}
doclen = {}; docpath = {}
for line in (M / "cases.tsv").read_text().splitlines():
    cid, repo, rev, kind, doc, _ = line.split("\t")
    p = subprocess.run(["git", "-C", REPOS[repo], "show", f"{rev}:{doc}"], capture_output=True, text=True)
    if p.returncode: print("fail", cid, p.stderr[:80]); continue
    doclen[cid] = p.stdout.count("\n"); docpath[cid] = doc
print("docs", len(doclen), "lines: min/median/max", min(doclen.values()), st.median(doclen.values()), max(doclen.values()))
R = json.load(open("reviews.json")); F = json.load(open("flaws2.json")); FL = json.load(open("flawline.json"))
# (a) where CONCERN/FAIL findings point, as a fraction of the document
pos = collections.defaultdict(list); last = collections.defaultdict(list)
for r in R:
    cid = r["case"]
    if cid not in doclen: continue
    d = json.load(open(M / "out" / f"{cid}-{r['alias']}-{r['run']}.json"))
    lines = []
    for f in d.get("findings", []):
        loc = str(f.get("location") or "")
        if pathlib.Path(docpath[cid]).name not in loc: continue
        m = re.search(r":(\d+)", loc)
        if not m: continue
        x = min(int(m.group(1)) / doclen[cid], 1.0); lines.append(x)
        if f.get("severity", "").upper() in ("CONCERN", "FAIL"): pos[r["alias"]].append(x)
    if lines: last[r["alias"]].append(max(lines))
print(f"\n{'config':16}{'n':>6}  share of CONCERN/FAIL findings pointing into each fifth of the document      median deepest line cited")
for a in ["fable-high", "fable-medium", "haiku-xhigh", "opus-high", "opus-medium", "sonnet-high", "sonnet-medium", "hy4", "minimax31-flash", "glm-flash", "mimo"]:
    xs = pos[a]; q = [sum(1 for x in xs if i / 5 <= x < (i + 1) / 5 or (i == 4 and x == 1.0)) / len(xs) for i in range(5)]
    print(f"{a:16}{len(xs):>6}  " + "  ".join(f"{v:5.0%}" for v in q) + f"      {st.median(last[a]):.0%}")
# (b) hit rate by flaw position (flaws with a known line only) and (c) by document length
obs = []
for r in R:
    for k, f in F.items():
        c, fid = k.split("/")
        if c == r["case"] and c in doclen:
            obs.append((r["alias"], k, int(fid in r["hit"]), (st.median(FL[k]) / doclen[c]) if k in FL else None, doclen[c]))
CL = ("haiku-xhigh", "opus-high", "opus-medium", "fable-medium", "fable-high", "sonnet-high", "sonnet-medium")
for label, sel in (("Claude configs", lambda a: a in CL), ("haiku-xhigh", lambda a: a == "haiku-xhigh"), ("others", lambda a: a not in CL)):
    line = f"{label:16} by flaw position:"
    for lo, hi in ((0, .33), (.33, .66), (.66, 1.01)):
        xs = [h for a, k, h, p, n in obs if sel(a) and p is not None and lo <= min(p, 1) < hi]
        line += f"  {lo:.0%}-{min(hi, 1):.0%}: {st.mean(xs):.0%} ({len({k for a, k, h, p, n in obs if p is not None and lo <= min(p, 1) < hi})} flaws)"
    print(line)
ls = sorted(doclen.values()); t1, t2 = ls[len(ls) // 3], ls[2 * len(ls) // 3]
for label, sel in (("Claude configs", lambda a: a in CL), ("haiku-xhigh", lambda a: a == "haiku-xhigh"), ("others", lambda a: a not in CL)):
    line = f"{label:16} by doc length:"
    for name, lo, hi in ((f"<{t1} lines", 0, t1), (f"{t1}-{t2}", t1, t2), (f">{t2}", t2, 10**9)):
        xs = [h for a, k, h, p, n in obs if sel(a) and lo <= n < hi]
        line += f"  {name}: {st.mean(xs):.0%} ({len({k for a, k, h, p, n in obs if lo <= n < hi})} flaws)"
    print(line)
