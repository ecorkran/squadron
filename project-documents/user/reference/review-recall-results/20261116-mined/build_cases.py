"""Parse the mined case files into cases.tsv: id repo reviewed_commit kind doc."""
import re, json, pathlib, collections, sys
REF = pathlib.Path(__file__).resolve().parents[2]            # .../reference
SCR = pathlib.Path(sys.argv[1])                              # scratchpad with batch*.json
FILES = ["design-review-recall-cases-2.md","design-review-recall-cases-3.md",
         "design-review-recall-cases-context-forge.md","design-review-recall-cases-migratory.md"]
JSONS = {"squadron":["batch1.json","batch2.json"],"context-forge":["batch-context-forge.json"],"migratory":["batch-migratory.json"]}
docs = collections.defaultdict(set)
for repo, names in JSONS.items():
    for n in names:
        for o in json.load(open(SCR/n)):
            nnn = re.match(r"(\d+)", o["review"]).group(1)
            docs[(repo,nnn,o["type"])].add((o["doc"], o["review"]))
rows, skipped = [], []
for fn in FILES:
    text = (REF/fn).read_text()
    for sec in re.split(r"\n(?=## \d+\. )", text)[1:]:
        m = re.match(r"## \d+\. (\S+)", sec)
        if not m: continue
        cid = m.group(1); mm = re.match(r"(squadron|context-forge|migratory)-(\d+)-(design|slice|tasks|arch)$", cid)
        if not mm: skipped.append((cid,"id")); continue
        repo, nnn, suffix = mm.groups(); kind = {"design":"slice"}.get(suffix, suffix)
        nvalid = len(re.findall(r"\*\*VALID", sec))
        if nvalid == 0: skipped.append((cid,"no valid flaw")); continue
        rc = re.search(r"reviewed-at:\s*`([0-9a-f]{7,40}\^?)`", sec)
        if not rc: skipped.append((cid,"no reviewed-at")); continue
        cands = docs.get((repo,nnn,kind), set())
        if len(cands) > 1:
            part = re.search(r"part-\d", sec); cands = {c for c in cands if part and part.group(0) in c[1]} or cands
        docpaths = {c[0] for c in cands}
        dm = re.search(rf"repo {repo}; `([^`]+)`", sec)
        if dm: docpaths = {dm.group(1)}
        if len(docpaths) != 1: skipped.append((cid,f"doc ambiguous/unknown {sorted(docpaths)}")); continue
        rows.append((cid, repo, rc.group(1), kind, docpaths.pop(), nvalid))
out = pathlib.Path(__file__).parent/"cases.tsv"
out.write_text("".join("\t".join(map(str,r))+"\n" for r in rows))
print(len(rows),"cases;", sum(r[5] for r in rows),"VALID markers"); print("skipped:", skipped)
