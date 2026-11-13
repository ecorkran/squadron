"""Collect CONCERN/FAIL findings per case for the precision pass."""
import glob, json, collections
CONFIGS = ("haiku-xhigh", "sol", "sonnet-high", "sonnet")
counts = collections.Counter()
by_case = collections.defaultdict(list)
for f in sorted(glob.glob("*-*-[123].json")):
    case, rest = f[:-5].split("-", 1)
    alias, run = rest.rsplit("-", 1)
    if alias not in CONFIGS:
        continue
    for i, x in enumerate(json.load(open(f))["findings"]):
        if x.get("severity") not in ("CONCERN", "FAIL"):
            continue
        by_case[case].append({
            "ref": f"{alias}/{run}/{i}", "severity": x["severity"],
            "title": x.get("title"), "location": x.get("location"),
            "description": x.get("description"),
        })
        counts[alias] += 1
for case, items in by_case.items():
    json.dump(items, open(f"precision/{case}-findings.json", "w"), indent=1)
    print(case, len(items))
print(dict(counts))
