"""Add one squadron entry to the harness's benchmark_data.json: convert.py DATA_JSON TOOL_NAME REVIEWER[,REVIEWER] [COMB_ALIAS|-] [SEVERITIES] [title|full] [CATEGORIES].

The entry's comments are the CONCERN and FAIL findings of the named reviewers (after the comb, when one is given),
one comment per finding with its path and line. SEVERITIES (default CONCERN,FAIL) widens what is sent;
"title" sends each finding's title alone, so the harness's issue extractor sees one claim per finding. A PR where any named reviewer has no output is left out and reported.
"""
import json, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent
data_path, tool, reviewers = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
comb = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
ACTED_ON = tuple(sys.argv[5].upper().split(",")) if len(sys.argv) > 5 else ("CONCERN", "FAIL")
title_only = len(sys.argv) > 6 and sys.argv[6] == "title"
categories = set(sys.argv[7].split(",")) if len(sys.argv) > 7 else None  # keep only findings the reviewer filed under these categories
data = json.load(open(data_path)); cases = json.load(open(HERE / "cases.json"))
added = comments = 0; missing = []
for url, entry in data.items():
    entry["reviews"] = [r for r in entry["reviews"] if r["tool"] != tool]
    case = cases.get(url)
    outs = [HERE / "out" / f"{case['name']}-{r.split(':')[0]}-{(r.split(':') + ['1'])[1]}.json" for r in reviewers] if case else []  # a reviewer is LABEL or LABEL:RUN
    combs = [HERE / "comb" / comb / p.name for p in outs] if comb else []
    if not case or not all(p.exists() for p in outs + combs):
        missing.append(url); continue
    review_comments = []
    for n, path in enumerate(outs):
        findings = json.loads(path.read_text())["findings"]
        kept = set(json.loads(combs[n].read_text())["kept"]) if comb else None
        for i, f in enumerate(findings):
            if str(f.get("severity", "")).upper() not in ACTED_ON or (kept is not None and i not in kept) or (categories is not None and str(f.get("category")) not in categories):
                continue
            m = re.match(r"\s*`?([^:`\s]+):(\d+)", str(f.get("location") or ""))
            review_comments.append({"path": m.group(1) if m else None, "line": int(m.group(2)) if m else None, "body": f["title"] if title_only else f"{f['title']}\n\n{f['description']}"})
    entry["reviews"].append({"tool": tool, "repo_name": case["name"], "pr_url": url, "review_comments": review_comments})
    added += 1; comments += len(review_comments)
json.dump(data, open(data_path, "w"), indent=1)
print(f"{tool}: {added} PRs, {comments} comments ({comments / max(1, added):.1f} per PR); left out: {len(missing)}", *missing[:5], sep="\n")
