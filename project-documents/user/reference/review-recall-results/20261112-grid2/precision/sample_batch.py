"""Draw a seeded random sample of graded issues and write one batch for a sorting agent.

Each item carries its member findings' text and the case's repo, base, head and worktree,
but not the earlier grade, so the sorting is independent of the original pass.

Usage: sample_batch.py <seed> <count> <out-file>
"""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRID = HERE.parent
WORKTREES = Path("/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/"
                 "7696a7eb-09da-49aa-be7f-09187995ae4e/scratchpad/wt")
FIELDS = ("ref", "severity", "title", "location", "description")


def load_cases() -> dict[str, dict[str, str]]:
    rows = [line.split() for line in (GRID / "cases.txt").read_text().splitlines() if line.strip()]
    return {case: {"repo": repo, "base": base, "head": head, "worktree": str(WORKTREES / case)}
            for case, repo, base, head in rows}


def load_issues() -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for path in sorted(HERE.glob("*-graded.json")):
        data = json.loads(path.read_text())
        for issue in data["issues"]:
            issues.append({"id": issue["id"], "case": data["case"], "members": issue["members"]})
    return issues


def member_text(case: str, refs: list[str]) -> list[dict[str, str]]:
    findings = {f["ref"]: f for f in json.loads((HERE / f"{case}-findings.json").read_text())}
    return [{k: findings[ref][k] for k in FIELDS} for ref in refs]


def already_drawn() -> set[str]:
    """Ids in earlier batches, so no issue is sorted twice."""
    drawn: set[str] = set()
    for path in (HERE / "sample").glob("batch*-input.json"):
        drawn.update(item["id"] for item in json.loads(path.read_text())["items"])
    return drawn


def main() -> None:
    seed, count, out_file = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    remaining = [i for i in load_issues() if i["id"] not in already_drawn()]
    chosen = random.Random(seed).sample(remaining, count)
    cases = load_cases()
    items = [{"id": i["id"], "case": i["case"], "members": member_text(str(i["case"]), list(i["members"]))}
             for i in chosen]
    used = sorted({str(i["case"]) for i in chosen})
    out_file.write_text(json.dumps({"cases": {c: cases[c] for c in used}, "items": items}, indent=1))
    print(f"wrote {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
