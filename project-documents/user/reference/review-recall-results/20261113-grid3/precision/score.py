"""Score graded findings, run 1 only, per config and case set.

Sources, merged: grid 2 grades (issues I*), grid 3 batch 1 and new-case grades
(`{case}-graded.json`, issues N*), grid 3 batch 2 (`{case}-graded-b2.json`, issues M*).
Known bugs hit counts issues whose `known` starts with B: those are proven by fix
commits, so that column does not depend on agent grading.
"""

import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GRID2 = os.path.join(HERE, "..", "..", "20261112-grid2", "precision")
GRADES = ("REAL", "MINOR", "FALSE", "PREEXISTING", "UNSURE")
ORIGINAL = "175 188 197 225 227 307 921 932 a122 u103".split()
KNOWN_TOTAL = {"original": 14, "new": 7}


def load() -> dict[tuple[str, str], dict]:
    """(case, ref) -> graded issue."""
    by_id: dict[tuple[str, str], dict] = {}
    by_ref: dict[tuple[str, str], dict] = {}
    for path in glob.glob(os.path.join(GRID2, "*-graded.json")):
        data = json.load(open(path))
        for issue in data["issues"]:
            by_id[(data["case"], issue["id"])] = issue
            for ref in issue["members"]:
                by_ref[(data["case"], ref)] = issue
    for pattern in ("*-graded.json", "*-graded-b2.json"):  # b2 may match N* ids, so N* first
        for path in sorted(glob.glob(os.path.join(HERE, pattern))):
            data = json.load(open(path))
            case = data["case"]
            for issue in data["new_issues"]:
                by_id[(case, issue["id"])] = issue
                for ref in issue["members"]:
                    by_ref[(case, ref)] = issue
            for ref, issue_id in data["matched"].items():
                by_ref[(case, ref)] = by_id[(case, issue_id)]
    return by_ref


def table(by_ref: dict[tuple[str, str], dict], case_set: str) -> None:
    rows = collections.defaultdict(lambda: {"n": 0, "g": collections.Counter(), "real": set(), "known": set(), "cases": set()})
    for (case, ref), issue in by_ref.items():
        config, run, _ = ref.split("/")
        if run != "1" or (case in ORIGINAL) != (case_set == "original"):
            continue
        row = rows[config]
        row["n"] += 1
        row["cases"].add(case)
        row["g"][issue["grade"]] += 1
        if issue["grade"] == "REAL":
            row["real"].add((case, issue["id"]))
        if (issue.get("known") or "").startswith("B"):
            row["known"].add((case, issue["known"]))
    print(f"\n### {case_set} cases, run 1 ({KNOWN_TOTAL[case_set]} known bugs)\n")
    print("| Config | Cases with findings | Findings | " + " | ".join(GRADES)
          + " | Precision | Distinct REAL | Known bugs hit |")
    print("|---|---|---|" + "---|" * len(GRADES) + "---|---|---|")
    for config, row in sorted(rows.items(), key=lambda kv: (-len(kv[1]["known"]), -len(kv[1]["real"]))):
        n = row["n"]
        print(f"| {config} | {len(row['cases'])} | {n} | " + " | ".join(str(row["g"][g]) for g in GRADES)
              + f" | {row['g']['REAL'] / n:.0%} | {len(row['real'])} | {len(row['known'])} |")


if __name__ == "__main__":
    graded = load()
    table(graded, "original")
    table(graded, "new")
