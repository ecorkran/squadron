"""Score graded grid 3 findings beside grid 2's, run 1 only, original 10 cases.

Per config: CONCERN/FAIL findings, grades, precision (REAL/all), distinct REAL issues
found, and known bugs hit (B* issues, graded by fix commits, so not agent-dependent).
"""

import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GRID2 = os.path.join(HERE, "..", "..", "20261112-grid2", "precision")
GRADES = ("REAL", "MINOR", "FALSE", "PREEXISTING", "UNSURE")


def issues_by_ref() -> dict[tuple[str, str], dict]:
    """(case, ref) -> issue, across grid 2 grades and grid 3 matches/new issues."""
    out: dict[tuple[str, str], dict] = {}
    old: dict[tuple[str, str], dict] = {}
    for path in glob.glob(os.path.join(GRID2, "*-graded.json")):
        data = json.load(open(path))
        for issue in data["issues"]:
            old[(data["case"], issue["id"])] = issue
            for ref in issue["members"]:
                out[(data["case"], ref)] = issue
    for path in glob.glob(os.path.join(HERE, "*-graded.json")):
        data = json.load(open(path))
        case = data["case"]
        for ref, issue_id in data["matched"].items():
            out[(case, ref)] = old[(case, issue_id)]
        for issue in data["new_issues"]:
            for ref in issue["members"]:
                out[(case, ref)] = issue
    return out


def main() -> None:
    graded = issues_by_ref()
    cases = {os.path.basename(p).split("-")[0] for p in glob.glob(os.path.join(HERE, "*-graded.json"))}
    rows = collections.defaultdict(lambda: {"n": 0, "grades": collections.Counter(), "real": set(), "known": set()})
    for (case, ref), issue in graded.items():
        config, run, _ = ref.split("/")
        if run != "1" or case not in cases:
            continue
        row = rows[config]
        row["n"] += 1
        row["grades"][issue["grade"]] += 1
        if issue["grade"] == "REAL":
            row["real"].add((case, issue["id"]))
        if (issue.get("known") or "").startswith("B"):
            row["known"].add((case, issue["known"]))
    print(f"Cases: {len(cases)}. Run 1 only. Known bugs in these cases: 14.\n")
    print("| Config | Findings | " + " | ".join(GRADES) + " | Precision | Distinct REAL issues | Known bugs hit |")
    print("|---|---|" + "---|" * len(GRADES) + "---|---|---|")
    for config, row in sorted(rows.items(), key=lambda kv: -len(kv[1]["known"])):
        n = row["n"]
        print(f"| {config} | {n} | " + " | ".join(str(row["grades"][g]) for g in GRADES)
              + f" | {row['grades']['REAL'] / n:.0%} | {len(row['real'])} | {len(row['known'])} |")


if __name__ == "__main__":
    main()
