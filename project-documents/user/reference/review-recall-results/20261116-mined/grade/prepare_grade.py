"""Build blind grading inputs for grid 2: per case flaws.json + rNN.json (shuffled, names stripped) + map.json."""
import json, re, random, pathlib, collections
HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent
REF = MINED.parents[1]
SEED = 20261116
ALIASES = ["fable-medium","opus-medium","sonnet-medium","haiku-xhigh","opus-high","sonnet-high"]
FILES = ["design-review-recall-cases-2.md","design-review-recall-cases-3.md",
         "design-review-recall-cases-context-forge.md","design-review-recall-cases-migratory.md"]
sections = {}
for fn in FILES:
    for sec in re.split(r"\n(?=## \d+\. )", (REF/fn).read_text())[1:]:
        m = re.match(r"## \d+\. (\S+)", sec)
        if m: sections[m.group(1)] = sec
cases = [l.split("\t") for l in (MINED/"cases.tsv").read_text().splitlines()]
rng = random.Random(SEED); mapping = {}; kinds = {}
for cid, repo, sha, kind, doc, nvalid in cases:
    kinds[cid] = kind
    flaws = []
    for line in sections[cid].splitlines():
        if line.startswith("  - ") and "**VALID" in line:
            t = line[4:]
            t = re.sub(r"\s*Not raised[^.]*\.?", "", t)           # drop original-review attribution
            flaws.append({"id": f"F{len(flaws)+1}", "text": t.strip()})
    assert flaws, cid
    d = HERE/cid; d.mkdir(exist_ok=True)
    (d/"flaws.json").write_text(json.dumps({"case": cid, "kind": kind, "flaws": flaws}, indent=1))
    runs = []
    for a in ALIASES:
        p = MINED/"out"/f"{cid}-{a}-1.json"
        assert p.exists(), p
        runs.append((a, json.loads(p.read_text())))
    rng.shuffle(runs)
    for n, (a, r) in enumerate(runs, 1):
        rid = f"r{n:02d}"; mapping[f"{cid}/{rid}"] = {"alias": a, "run": 1, "kind": kind}
        fs = [{"i": i, "severity": f["severity"], "title": f["title"], "description": f["description"],
               "location": f.get("location")} for i, f in enumerate(r["findings"]) if f["severity"] != "PASS"]
        (d/f"{rid}.json").write_text(json.dumps({"review": rid, "findings": fs}, indent=1))
(HERE/"map.json").write_text(json.dumps(mapping, indent=1))
print(len(cases), "cases;", sum(len(json.load(open(HERE/c[0]/"flaws.json"))["flaws"]) for c in cases), "flaws")
