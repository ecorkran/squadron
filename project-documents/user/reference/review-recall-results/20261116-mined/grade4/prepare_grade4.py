"""Blind grading inputs for the cheap OpenRouter reviewers (glm52, glm-flash, deepseek4-flash, minimax) run 1, with haiku-xhigh and fable-medium run 1 as calibration anchors: per case flaws.json + rNN.json (shuffled, names stripped) + map.json.

Run 1 grades live in ../grade and are left untouched; this set is graded separately.
"""
import json, pathlib, random, shutil

HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent
GRADE1 = MINED / "grade"
SEED = 20261119
ALIASES = ["glm52", "glm-flash", "deepseek4-flash", "minimax", "haiku-xhigh", "fable-medium"]
RUNS = (1,)

cases = [line.split("\t") for line in (MINED / "cases.tsv").read_text().splitlines()]
rng = random.Random(SEED)
mapping = {}
for cid, _repo, _sha, kind, _doc, _nvalid in cases:
    out_dir = HERE / cid
    out_dir.mkdir(exist_ok=True)
    shutil.copy(GRADE1 / cid / "flaws.json", out_dir / "flaws.json")
    runs = []
    for alias in ALIASES:
        for run in RUNS:
            path = MINED / "out" / f"{cid}-{alias}-{run}.json"
            assert path.exists(), path
            runs.append((alias, run, json.loads(path.read_text())))
    rng.shuffle(runs)
    for n, (alias, run, review) in enumerate(runs, 1):
        rid = f"r{n:02d}"
        mapping[f"{cid}/{rid}"] = {"alias": alias, "run": run, "kind": kind}
        findings = [
            {"i": i, "severity": f["severity"], "title": f["title"],
             "description": f["description"], "location": f.get("location")}
            for i, f in enumerate(review["findings"]) if f["severity"] != "PASS"
        ]
        (out_dir / f"{rid}.json").write_text(json.dumps({"review": rid, "findings": findings}, indent=1))
(HERE / "map.json").write_text(json.dumps(mapping, indent=1))
print(len(cases), "cases,", len(mapping), "reviews")
