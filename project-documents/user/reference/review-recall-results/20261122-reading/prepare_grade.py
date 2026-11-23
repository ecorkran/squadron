"""Blind grading piles for the reading run: prepare_grade.py PILE_DIR.

Per case: flaws.json (the key of ../20261116-mined/grade) and rNN.json, shuffled with names stripped.
Each pile holds the six new reviews of the case (this folder's out/, current templates) and the
stored run 1 of the same four reviewers (../20261116-mined/out, squadron 0.24.31), so one grader
scores old and new together. The piles go to PILE_DIR, outside this folder; map.json stays here,
where a grader working in a pile cannot see it.
"""
import json, pathlib, random, shutil, sys

HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent / "20261116-mined"
SEED = 20261122
NEW = [("haiku-xhigh", 1), ("haiku-xhigh", 2), ("sonnet-high", 1), ("sonnet-high", 2), ("opus-high", 1), ("fable-high", 1)]
STORED = [("haiku-xhigh", 1), ("sonnet-high", 1), ("opus-high", 1), ("fable-high", 1)]
piles = pathlib.Path(sys.argv[1])
rng = random.Random(SEED)
mapping = {}
for line in (MINED / "cases.tsv").read_text().splitlines():
    cid, _repo, _sha, kind, _doc, _nvalid = line.split("\t")
    pile = piles / cid
    shutil.rmtree(pile, ignore_errors=True); pile.mkdir(parents=True)
    shutil.copy(MINED / "grade" / cid / "flaws.json", pile / "flaws.json")
    runs = []
    for arm, folder, wanted in (("new", HERE / "out", NEW), ("stored", MINED / "out", STORED)):
        for alias, run in wanted:
            path = folder / f"{cid}-{alias}-{run}.json"
            # a missing output is a failed review, which must not be silently dropped
            assert path.exists(), path
            runs.append((arm, alias, run, json.loads(path.read_text())))
    rng.shuffle(runs)
    for n, (arm, alias, run, review) in enumerate(runs, 1):
        rid = f"r{n:02d}"
        mapping[f"{cid}/{rid}"] = {"arm": arm, "alias": alias, "run": run, "kind": kind}
        findings = [
            {"i": i, "severity": f["severity"], "title": f["title"],
             "description": f["description"], "location": f.get("location")}
            for i, f in enumerate(review["findings"]) if f["severity"] != "PASS"
        ]
        (pile / f"{rid}.json").write_text(json.dumps({"review": rid, "findings": findings}, indent=1))
(HERE / "map.json").write_text(json.dumps(mapping, indent=1))
print(len({key.split("/")[0] for key in mapping}), "cases,", len(mapping), "reviews")
