import re, subprocess, pathlib, collections, json, sys
ROOT = pathlib.Path(sys.argv[1]); OUT = sys.argv[2]
def git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True); return r.returncode, r.stdout
def fm(t):
    m = re.match(r"---\n(.*?)\n---", t, re.S); d = {}
    if m:
        for l in m.group(1).splitlines():
            k,_,v = l.partition(":"); d[k.strip()] = v.strip()
    return d
CORR = re.compile(r"\b(correct|align|amend|revise|replace|drop|tighten|fix|bound|resolve)\b", re.I)
NOISE = re.compile(r"address|review round|cf check|^test|check off|task progress", re.I)
tot = collections.Counter(); out = []; dates = collections.Counter()
for f in sorted((ROOT/"project-documents/user/reviews").glob("*review.*.md")):
    d = fm(f.read_text()); t = d.get("reviewType") or d.get("targetKind") or ""
    if t not in ("slice","tasks","arch"): tot["other_type"] += 1; continue
    tot[t+" reviews"] += 1
    sha, doc = d.get("reviewedSha",""), d.get("sourceDocument","")
    if not sha: tot[t+" no_sha"] += 1; dates[d.get("dateCreated","?")[:6]] += 1; continue
    if git("cat-file","-e",sha+"^{commit}")[0]: tot[t+" sha_missing"] += 1; continue
    if not doc: tot[t+" no_doc"] += 1; continue
    if git("cat-file","-e",f"{sha}:{doc}")[0]: tot[t+" doc_absent_at_sha"] += 1; continue
    tot[t+" usable_sha"] += 1
    ct = git("show","-s","--format=%ct",sha)[1].strip()
    log = git("log","--reverse","--format=%H %ct %s","--",doc)[1]
    corr = []
    for l in log.splitlines():
        h,c,s = l.split(" ",2)
        if int(c) <= int(ct): continue
        files = git("show","--name-only","--format=",h)[1]
        if any("/reviews/" in x for x in files.splitlines()): continue
        if re.match(r"(feat|fix)", s): continue
        if CORR.search(s) and not NOISE.search(s): corr.append((h[:8], s))
    if corr:
        tot[t+" correction_candidates"] += 1
        out.append({"review":f.name,"type":t,"reviewedSha":sha,"doc":doc,"model":d.get("aiModel"),"correcting_commits":corr})
json.dump(out, open(OUT,"w"), indent=1)
for k,v in sorted(tot.items()): print(k, v)
print("no_sha by month", sorted(dates.items()))
for o in out: print(o["type"], o["review"][:50], "|", o["correcting_commits"][0][1][:70])
