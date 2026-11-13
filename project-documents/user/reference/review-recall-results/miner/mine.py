"""Mine review-recall leads: fix commits whose fixed lines came from a reviewed range.

Usage: mine.py <repo-path> [--since YYYY-MM-DD] [--window 40] > leads.json

For each `fix:` commit (subjects mentioning a review are skipped), blame the parent on the
lines the fix deleted or changed (non-test source files only) to find the commits that
introduced them. A lead with a review: an introducing commit is an ancestor of a saved code
review's reviewedSha, within --window commits of it, and the fix lands after that sha.
Leads without a matching review are kept with head = the introducing commit (a single
commit diff). Mined output over-reports; every lead must be read before it becomes a case.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures)/|[._-](test|spec)\.[a-z]+$|^test_")
SOURCE_EXT = re.compile(r"\.(py|ts|tsx|js|jsx|mjs|sh|rs|go|sql|yaml|yml|toml)$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def git(repo: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)
    return out.stdout


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b]).returncode == 0


def reviews(repo: Path) -> list[dict[str, str]]:
    found = []
    for path in git(repo, "ls-files").splitlines():
        if "reviews/" not in path or "review.code" not in path or "fixtures" in path:
            continue
        text = (repo / path).read_text(errors="replace")[:3000]
        if m := re.search(r"^reviewedSha:\s*([0-9a-f]{7,40})", text, re.MULTILINE):
            found.append({"file": path, "sha": m.group(1)})
    return found


def fixed_lines(repo: Path, fix: str) -> dict[str, list[tuple[int, int]]]:
    """Parent-side line ranges the fix deleted or changed, per source file."""
    ranges: dict[str, list[tuple[int, int]]] = {}
    current = None
    for line in git(repo, "diff", "-U0", f"{fix}^", fix).splitlines():
        if line.startswith("--- "):
            path = line[6:] if line.startswith("--- a/") else None
            ok = path and SOURCE_EXT.search(path) and not TEST_PATH.search(path)
            current = path if ok else None
        elif current and (m := HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or "1")
            if count:
                ranges.setdefault(current, []).append((start, start + count - 1))
    return ranges


def introducers(repo: Path, fix: str) -> set[str]:
    shas: set[str] = set()
    for path, spans in fixed_lines(repo, fix).items():
        for start, end in spans:
            out = git(repo, "blame", "--porcelain", "-L", f"{start},{end}", f"{fix}^", "--", path,
                      check=False)
            shas.update(m.group(1) for m in re.finditer(r"^([0-9a-f]{40}) \d+ \d+", out, re.MULTILINE))
    return shas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("--since", default="2025-01-01")
    parser.add_argument("--window", type=int, default=40)
    args = parser.parse_args()
    repo = args.repo.resolve()
    saved = reviews(repo)
    log = git(repo, "log", f"--since={args.since}", "--format=%H%x09%ad%x09%s", "--date=short")
    leads = []
    for row in log.splitlines():
        fix, date, subject = row.split("\t", 2)
        if not subject.startswith("fix") or re.search(r"review|finding", subject, re.IGNORECASE):
            continue
        intro = introducers(repo, fix)
        if not intro:
            continue
        matched = []
        for review in saved:
            sha = review["sha"]
            if not is_ancestor(repo, sha, fix) or sha == fix:
                continue
            buggy = [i for i in intro if is_ancestor(repo, i, sha)
                     and int(git(repo, "rev-list", "--count", f"{i}..{sha}")) <= args.window]
            if buggy:
                matched.append({"review": review["file"], "head": sha, "buggy": buggy})
        lead = {"repo": repo.name, "fix": fix[:10], "date": date, "subject": subject,
                "introducers": sorted(i[:10] for i in intro)}
        if matched:
            best = min(matched, key=lambda m: int(git(repo, "rev-list", "--count", f"{m['head']}..{fix}")))
            earliest = min(best["buggy"], key=lambda i: int(git(repo, "rev-list", "--count", i)))
            lead.update(review=best["review"], head=best["head"][:10], base=f"{earliest[:10]}^")
        else:
            newest = max(intro, key=lambda i: int(git(repo, "rev-list", "--count", i)))
            lead.update(review=None, head=newest[:10], base=f"{newest[:10]}^")
        leads.append(lead)
    print(json.dumps(leads, indent=1))


if __name__ == "__main__":
    main()
