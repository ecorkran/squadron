"""Compare the sampled items' grades across the original agent pass and the regrade runs.

Prints, per grader, how often it matches the original grade and the other regrades, and
lists the items where the graders disagree. Those are the items worth a hand label.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRECISION = HERE.parent
RUNS = ["sonnet-medium", "sonnet-high"]  # regrade files; each has an A and a B half


def load_runs() -> dict[str, dict[str, str]]:
    grades: dict[str, dict[str, str]] = {}
    for run in RUNS:
        grades[run] = {}
        for group in ("A", "B"):
            for row in json.loads((HERE / f"{run}-{group}.json").read_text()):
                grades[run][row["id"]] = row["grade"]
    return grades


def main() -> None:
    original = {row["id"]: row["agent_grade"] for row in json.loads((PRECISION / "labels-sample.json").read_text())}
    regrades = load_runs()
    graders = {"original": original, **regrades}
    print("| Grader | Matches original | Matches the other regrade |")
    print("|---|---|---|")
    for name, grades in graders.items():
        others = [g for n, g in regrades.items() if n != name]
        same_original = sum(grades[i] == original[i] for i in original)
        same_other = sum(grades[i] == other[i] for other in others for i in original) if others else 0
        other_total = sum(len(original) for _ in others)
        print(f"| {name} | {same_original} of {len(original)} | {same_other} of {other_total} |" if others
              else f"| {name} | {same_original} of {len(original)} | n/a |")
    print("\nItems where the graders disagree (grade by each grader):")
    for item_id in original:
        row = {name: grades[item_id] for name, grades in graders.items()}
        if len(set(row.values())) > 1:
            cells = ", ".join(f"{name} {grade}" for name, grade in row.items())
            print(f"- {item_id}: {cells}")


if __name__ == "__main__":
    main()
