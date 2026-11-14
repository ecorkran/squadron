"""Build the regrade inputs for the 30 sampled issues: finding text only, no earlier grades.

Writes regrade/input-A.json and regrade/input-B.json, one per group of cases, for the
grading agents. Each item lists the issue id, its member findings (ref, severity, title,
location, description), and the case's repo, base, head and worktree. The earlier grade is
deliberately left out so the regrade is independent.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
WORKTREES = Path("/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/"
                 "7696a7eb-09da-49aa-be7f-09187995ae4e/scratchpad/wt")
GROUPS = {"A": ["175", "188", "197", "225", "227"], "B": ["307", "921", "932", "a122", "u103"]}
FIELDS = ("ref", "severity", "title", "location", "description")


def load_cases() -> dict[str, dict[str, str]]:
    rows = [line.split() for line in (RESULTS / "cases.txt").read_text().splitlines()
            if line.strip()]
    return {case: {"repo": repo, "base": base, "head": head, "worktree": str(WORKTREES / case)}
            for case, repo, base, head in rows}


def issue_members(case: str, issue_id: str) -> list[str]:
    data = json.loads((HERE / f"{case}-graded.json").read_text())
    for issue in data["issues"]:
        if issue["id"] == issue_id:
            return list(issue["members"])
    raise KeyError(f"{issue_id} not in {case}-graded.json")


def main() -> None:
    sample = json.loads((HERE / "labels-sample.json").read_text())
    cases = load_cases()
    out_dir = HERE / "regrade"
    out_dir.mkdir(exist_ok=True)
    for group, group_cases in GROUPS.items():
        items = []
        for entry in sample:
            if entry["case"] not in group_cases:
                continue
            case = entry["case"]
            findings = {f["ref"]: f for f in json.loads((HERE / f"{case}-findings.json").read_text())}
            members = [{k: findings[ref][k] for k in FIELDS} for ref in issue_members(case, entry["id"])]
            items.append({"id": entry["id"], "case": case, "members": members})
        payload = {"cases": {c: cases[c] for c in group_cases}, "items": items}
        (out_dir / f"input-{group}.json").write_text(json.dumps(payload, indent=1))
        print(f"group {group}: {len(items)} items")


if __name__ == "__main__":
    main()
