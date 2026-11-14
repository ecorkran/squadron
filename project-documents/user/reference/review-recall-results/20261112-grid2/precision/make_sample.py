"""Draw a stratified sample of graded issues for hand labeling, and write the sheet.

Writes LABELS-SAMPLE.md (the sheet a person fills in) and labels-sample.json
(the agent grades, kept as the comparison key). Re-running with the same seed
gives the same sample.
"""

import glob
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
WORKTREES = Path("/private/tmp/claude-501/-Users-manta-source-repos-manta-squadron/"
                 "7696a7eb-09da-49aa-be7f-09187995ae4e/scratchpad/wt")
SEED = 20261113
# How many issues to draw per agent grade. FALSE is taken whole; REAL is over-sampled
# because a missed REAL is the costly error for a comb or a precision figure.
QUOTA = {"FALSE": 7, "REAL": 12, "MINOR": 6, "PREEXISTING": 3, "UNSURE": 2}
CONTEXT_LINES = 3  # lines shown before and after each cited range
MAX_SNIPPET_LINES = 40  # cap per cited range so the sheet stays readable


def load_issues() -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for path in sorted(HERE.glob("*-graded.json")):
        data = json.loads(path.read_text())
        for issue in data["issues"]:
            issues.append({**issue, "case": data["case"]})
    return issues


def draw(issues: list[dict[str, object]]) -> list[dict[str, object]]:
    rng = random.Random(SEED)
    chosen: list[dict[str, object]] = []
    for grade, count in QUOTA.items():
        pool = sorted((i for i in issues if i["grade"] == grade), key=lambda i: str(i["id"]))
        chosen.extend(pool if count >= len(pool) else rng.sample(pool, count))
    rng.shuffle(chosen)
    return chosen


def code_text(case: str, item: str) -> str:
    """The cited lines from the case's head worktree, numbered, with a little context.

    An item may cite several ranges after one path ("file.py:154,194-200"). Cited lines
    are marked with ">". A path that is missing at head is reported, not skipped.
    """
    path_text, _, spans = item.rpartition(":")
    source = WORKTREES / case / path_text
    if not source.is_file():
        return f"not found at head ({source})"
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks = []
    for span in spans.split(","):
        start_text, _, end_text = span.strip().partition("-")
        start = int(start_text)
        end = int(end_text) if end_text else start
        lo = max(1, start - CONTEXT_LINES)
        hi = min(len(lines), end + CONTEXT_LINES, lo + MAX_SNIPPET_LINES - 1)
        blocks.append("\n".join(
            f"{'>' if start <= n <= end else ' '} {n:5d}  {lines[n - 1]}" for n in range(lo, hi + 1)
        ))
    return "\n...\n".join(blocks)


def snippet(case: str, item: str) -> str:
    """Markdown for the sheet: the cited code in a fenced block, labeled with its reference."""
    return f"`{item}`\n\n```\n{code_text(case, item)}\n```"


def sheet(sample: list[dict[str, object]]) -> str:
    lines = [
        "# Hand labels, grid 2 precision sample",
        "",
        "Label each claim by reading the code it cites at head. Write one word after `Human:`:",
        "REAL (should be fixed before merge), MINOR (true, low value), FALSE (the claim is wrong),",
        "PREEXISTING (true but not caused by the change), UNSURE (you cannot tell).",
        "The agent grade is hidden in the answer key until you finish, so label first.",
        "",
        f"Worktrees at each case head: `{WORKTREES}/<case>`.",
        "",
        f"{len(sample)} issues. Definitions: `precision/BRIEF.md`.",
        "",
    ]
    for n, issue in enumerate(sample, 1):
        evidence = issue["evidence"]
        if not isinstance(evidence, list):
            raise TypeError(f"{issue['id']}: evidence is {type(evidence).__name__}, expected list")
        lines += [
            f"## {n}. {issue['id']}",
            "",
            f"**{issue['title']}**",
            "",
            f"Why (agent): {issue['why']}",
            "",
            "Code cited (head):",
            "",
        ]
        for item in evidence:
            lines += [snippet(str(issue["case"]), str(item)), ""]
        lines += [
            "Human: ",
            "",
            "Note: ",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    sample = draw(load_issues())
    (HERE / "LABELS-SAMPLE.md").write_text(sheet(sample))
    key = [{"n": n, "id": i["id"], "case": i["case"], "agent_grade": i["grade"]}
           for n, i in enumerate(sample, 1)]
    (HERE / "labels-sample.json").write_text(json.dumps(key, indent=1) + "\n")
    print(f"wrote {len(sample)} issues to LABELS-SAMPLE.md and labels-sample.json")


if __name__ == "__main__":
    main()
