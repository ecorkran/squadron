import re, subprocess, pathlib, collections, difflib, sys, json
ROOT = pathlib.Path(sys.argv[1]); OUTF = sys.argv[2]
def git(*a):
    r = subprocess.run(["git","-C",str(ROOT),*a], capture_output=True, text=True); return r.returncode, r.stdout
def fm(t):
    m = re.match(r"---\n(.*?)\n---", t, re.S); d = {}
    if m:
        for l in m.group(1).splitlines():
            k,_,v = l.partition(":"); d[k.strip()] = v.strip()
    return d
def norm(t): return [re.sub(r"\[[xX]\]","[ ]",l).rstrip() for l in t.splitlines()]
def nch(a,b): return sum(1 for l in difflib.unified_diff(norm(a),norm(b),lineterm="",n=0) if l[:1] in "+-" and l[:3] not in ("+++","---"))
c = collections.Counter(); out = []
for f in sorted((ROOT/"project-documents/user/reviews").glob("*review.*.md")):
    d = fm(f.read_text()); t = d.get("reviewType","")
    if t not in ("slice","tasks","arch"): continue
    c[t+" reviews"] += 1
    doc = d.get("sourceDocument","")
    if not doc:
        m = re.search(r"slice[s]?/(\d+-[^ ]+\.md)|(\d+)", f.name); c[t+" no_sourceDocument"] += 1; continue
    rel = "project-documents/user/reviews/"+f.name
    shas = git("log","--diff-filter=A","--format=%H","--",rel)[1].split()
    if not shas: c[t+" no_add_commit"] += 1; continue
    C = shas[-1]
    if d.get("reviewedSha") and git("cat-file","-e",d["reviewedSha"]+f":{doc}")[0]==0: ref=d["reviewedSha"]; how="sha"
    elif git("cat-file","-e",f"{C}^:{doc}")[0]==0 and nch(git("show",f"{C}^:{doc}")[1], git("show",f"{C}:{doc}")[1] if git("cat-file","-e",f"{C}:{doc}")[0]==0 else "")>=4: ref=C+"^"; how="parent_of_response"
    elif git("cat-file","-e",f"{C}:{doc}")[0]==0: ref=C; how="doc_at_review_commit"
    else: c[t+" doc_unrecoverable"] += 1; continue
    rc,new = git("show",f"HEAD:{doc}")
    if rc: c[t+" doc_gone_at_head"] += 1; continue
    ch = nch(git("show",f"{ref}:{doc}")[1], new)
    c[t+" recoverable_"+how] += 1
    if ch >= 6: c[t+" recoverable_and_changed_since"] += 1; out.append({"review":f.name,"type":t,"reviewedText":ref,"how":how,"doc":doc,"changed_since":ch,"model":d.get("aiModel")})
for k,v in sorted(c.items()): print(k,v)
json.dump(out,open(OUTF,"w"),indent=1)
