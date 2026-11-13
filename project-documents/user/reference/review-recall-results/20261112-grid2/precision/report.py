"""Score precision from the graded files and write REVIEW.md for a human pass."""
import collections, glob, json, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
GRADES = ("REAL", "MINOR", "FALSE", "PREEXISTING", "UNSURE")
CONFIGS = ("haiku-xhigh", "sol", "sonnet-high", "sonnet")
RUNS_PER_CONFIG = 30

findings = {}  # ref key -> severity
for f in glob.glob("*-findings.json"):
    case = f.split("-", 1)[0]
    for x in json.load(open(f)):
        findings[(case, x["ref"])] = x["severity"]

graded, issues_by_case = {}, {}
for f in sorted(glob.glob("*-graded.json")):
    d = json.load(open(f))
    case = d["case"]
    issues_by_case[case] = d["issues"]
    for issue in d["issues"]:
        for ref in issue["members"]:
            graded[(case, ref)] = issue

missing = [k for k in findings if k[0] in issues_by_case and k not in graded]
if missing:
    raise SystemExit(f"ungraded findings: {missing[:10]} ({len(missing)} total)")

by_config = collections.defaultdict(collections.Counter)
fails = collections.defaultdict(collections.Counter)
for (case, ref), issue in graded.items():
    config = ref.split("/")[0]
    by_config[config][issue["grade"]] += 1
    if findings[(case, ref)] == "FAIL":
        fails[config]["justified" if issue["grade"] == "REAL" and issue.get("fail_justified") else "not"] += 1

out = ["# Precision review, grid 2", "",
       f"Cases graded: {', '.join(sorted(issues_by_case))}. Findings are CONCERN and FAIL only.",
       "Grades are a first pass by one agent per case. Mark each issue below; disagreements change the table.", "",
       "| Config | Findings | REAL | MINOR | FALSE | PREEXISTING | UNSURE | Precision (REAL/all) | False rate | REAL per run | FAIL justified |",
       "|---|---|---|---|---|---|---|---|---|---|---|"]
for c in CONFIGS:
    n = sum(by_config[c].values())
    if not n:
        continue
    g = by_config[c]
    fj = fails[c]
    out.append(f"| {c} | {n} | " + " | ".join(str(g[x]) for x in GRADES)
               + f" | {g['REAL'] / n:.0%} | {g['FALSE'] / n:.0%} | {g['REAL'] / RUNS_PER_CONFIG:.1f}"
               + f" | {fj['justified']} of {fj['justified'] + fj['not']} |")
out.append("")

for case in sorted(issues_by_case):
    out += [f"## {case}", ""]
    order = {g: i for i, g in enumerate(("REAL", "FALSE", "UNSURE", "MINOR", "PREEXISTING"))}
    for issue in sorted(issues_by_case[case], key=lambda i: (order[i["grade"]], i["id"])):
        who = collections.Counter(m.split("/")[0] for m in issue["members"])
        sev = collections.Counter(findings[(case, m)] for m in issue["members"])
        known = f" — known {issue['known']}" if issue.get("known") else ""
        out += [f"### {issue['id']} · {issue['grade']} ({issue['confidence']}){known}",
                f"**{issue['title']}**", "",
                "Found by: " + ", ".join(f"{k} ×{v}" for k, v in sorted(who.items()))
                + " · " + ", ".join(f"{k} ×{v}" for k, v in sorted(sev.items())), "",
                issue["why"], "",
                "Evidence: " + ", ".join(f"`{e}`" for e in issue.get("evidence", [])), "",
                "- [ ] agree   - [ ] disagree →", ""]

open("REVIEW.md", "w").write("\n".join(out))
print("\n".join(out[:4 + 3 + len(CONFIGS)]))
