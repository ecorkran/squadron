# Blind grading brief (grade4)

You grade design reviews against a fixed list of known flaws.

For each case directory you are given:
- `flaws.json`: `{case, kind, flaws: [{id, text}]}`. Each flaw is a real, verified defect in the reviewed document.
- `rNN.json`: `{review, findings: [{i, severity, title, description, location}]}`. Reviews are anonymous; do not guess who wrote them.

For every flaw and every review, decide whether any finding in that review identifies the same defect. A finding counts when it names the same underlying problem, even in different words or at a different location. A finding that is merely about the same area, or that raises a different problem, does not count. Be strict but fair; when truly borderline, count it and say so in `note`.

Write `hits.json` in the case directory:

{"case": "<case id>", "flaws": [{"id": "F1", "text": "<flaw text>", "hits": {"r01": [<finding i values>], "r02": []}}], "note": "<borderline calls, or 'No borderline calls'>"}

Every flaw appears once. Every review appears under `hits` for every flaw, with an empty list when it did not find it. Use only the files in the case directory.
