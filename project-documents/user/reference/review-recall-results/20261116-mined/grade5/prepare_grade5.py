"""Blind grading inputs for the 20261117 design-review models (mimo, mimo-flash, hy4, hy4-flash,
minimax31-flash, qwen38-flash, qwen38-27b, luna-r-high on all 43 cases; glm53, kimi3, qwen38,
qwen38-max, terra-r, sol, luna, terra on the 15-case subset), with haiku-xhigh, fable-medium
and glm-flash run 1 as calibration anchors: per case flaws.json + rNN.json (shuffled, names
stripped) + map.json.

Earlier grades in ../grade, ../grade2 and ../grade4 are left untouched; this set is graded separately.
"""
import json, pathlib, random, shutil

HERE = pathlib.Path(__file__).resolve().parent
MINED = HERE.parent
GRADE1 = MINED / "grade"
SEED = 20261120
ANCHORS = ["haiku-xhigh", "fable-medium", "glm-flash"]
ALL_CASE_MODELS = ["mimo", "mimo-flash", "hy4", "hy4-flash", "minimax31-flash",
                   "qwen38-flash", "qwen38-27b", "luna-r-high"]
SUBSET_MODELS = ["glm53", "kimi3", "qwen38", "qwen38-max", "terra-r", "sol", "luna", "terra"]
RUN = 1

cases = [line.split("\t") for line in (MINED / "cases.tsv").read_text().splitlines()]
subset_ids = {row[0] for row in cases[::3]}
rng = random.Random(SEED)
mapping = {}
for cid, _repo, _sha, kind, _doc, _nvalid in cases:
    out_dir = HERE / cid
    out_dir.mkdir(exist_ok=True)
    shutil.copy(GRADE1 / cid / "flaws.json", out_dir / "flaws.json")
    aliases = ANCHORS + ALL_CASE_MODELS + (SUBSET_MODELS if cid in subset_ids else [])
    runs = []
    for alias in aliases:
        path = MINED / "out" / f"{cid}-{alias}-{RUN}.json"
        # a missing output is a failed or skipped review, which must not be silently dropped
        assert path.exists(), path
        runs.append((alias, json.loads(path.read_text())))
    rng.shuffle(runs)
    for n, (alias, review) in enumerate(runs, 1):
        rid = f"r{n:02d}"
        mapping[f"{cid}/{rid}"] = {"alias": alias, "run": RUN, "kind": kind}
        findings = [
            {"i": i, "severity": f["severity"], "title": f["title"],
             "description": f["description"], "location": f.get("location")}
            for i, f in enumerate(review["findings"]) if f["severity"] != "PASS"
        ]
        (out_dir / f"{rid}.json").write_text(json.dumps({"review": rid, "findings": findings}, indent=1))
(HERE / "map.json").write_text(json.dumps(mapping, indent=1))
print(len(cases), "cases,", len(mapping), "reviews,", len(subset_ids), "subset cases")
