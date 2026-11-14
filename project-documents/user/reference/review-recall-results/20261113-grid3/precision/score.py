"""Score graded findings, run 1 only, per config and case set.

Sources, merged: grid 2 grades (issues I*), grid 3 batch 1 and new-case grades
(`{case}-graded.json`, issues N*), grid 3 batch 2 (`{case}-graded-b2.json`, issues M*).
`{case}-graded-sol.json` (issues S*) grades the sol, sol-high and sol-xhigh findings that
runs 2 and 3 and the new cases added after the first pass. Known bugs hit counts issues whose `known` starts with B: those are proven by fix
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
    for pattern in ("*-graded.json", "*-graded-b2.json", "*-graded-sol.json"):  # later files may match earlier ids
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


SOL_ALIASES = ("sol", "sol-high", "sol-xhigh")


def table_all_runs(by_ref: dict[tuple[str, str], dict]) -> None:
    """Codex sol family, every run. Other configs have run 1 graded only."""
    reviews = collections.Counter()
    files = {os.path.basename(p) for d in (os.path.join(HERE, ".."), GRID2, os.path.join(GRID2, ".."))
             for p in glob.glob(os.path.join(d, "*-*-[0-9].json"))}  # grid 2 holds the sol runs of the original cases
    for name in files:
        case, rest = name[:-5].split("-", 1)
        config = rest.rsplit("-", 1)[0]
        if config in SOL_ALIASES:
            reviews[(config, "original" if case in ORIGINAL else "new")] += 1
    for case_set in ("original", "new"):
        print(f"\n### sol family, {case_set} cases, all runs ({KNOWN_TOTAL[case_set]} known bugs)\n")
        print("| Config | Reviews | Findings | " + " | ".join(GRADES)
              + " | Precision | Distinct REAL | Known bugs hit |")
        print("|---|---|---|" + "---|" * len(GRADES) + "---|---|---|")
        for config in SOL_ALIASES:
            items = [(c, r, i) for (c, r), i in by_ref.items()
                     if r.split("/")[0] == config and (c in ORIGINAL) == (case_set == "original")]
            if not items:
                continue
            grades = collections.Counter(i["grade"] for _, _, i in items)
            real = {(c, i["id"]) for c, _, i in items if i["grade"] == "REAL"}
            known = {(c, i["known"]) for c, _, i in items if (i.get("known") or "").startswith("B")}
            print(f"| {config} | {reviews[(config, case_set)]} | {len(items)} | "
                  + " | ".join(str(grades[g]) for g in GRADES)
                  + f" | {grades['REAL'] / len(items):.0%} | {len(real)} | {len(known)} |")


if __name__ == "__main__":
    graded = load()
    table(graded, "original")
    table(graded, "new")
    table_all_runs(graded)
