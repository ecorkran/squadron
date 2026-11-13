---
docType: reference
project: squadron
dateCreated: 20261113
dateUpdated: 20261113
status: draft
---

# Incremental precision grading brief (grid 3)

You are grading new code-review findings for one case. The same case was already graded in grid 2: its distinct issues, each with a grade, are in `../20261112-grid2/precision/{case}-graded.json`. Most new findings repeat an issue that is already graded. Reuse those grades; only grade what is genuinely new.

## Inputs
- New findings: `precision/{case}-findings.json` in this grid directory. Each has `ref` (`config/run/index`), `severity`, `title`, `location`, `description`.
- Existing issues: `../20261112-grid2/precision/{case}-graded.json` (relative to this grid directory). Grades and their rules are in `../20261112-grid2/precision/BRIEF.md`; read its grade definitions and apply them unchanged.
- Case repo, base and head: `../20261112-grid2/cases.txt` (`case repo base head`). Repos are at `/Users/manta/source/repos/manta/{repo}`. Known bugs: the case's section of `/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-cases.md`.

## Steps
1. For each new finding, decide whether it describes the same defect at the same place as an existing issue. If it does, assign it to that issue id. Match on substance, not wording. A finding on the same function but a different defect is a new issue.
2. Group the remaining findings into new issues and grade each one against the code at `head` exactly as the grid 2 brief says (read-only: `git -C {repo} show {head}:{path}`, `git diff {base} {head}`; never check out, stash, reset or edit).
3. If a matched existing issue's grade now looks wrong to you, do not change it; list its id under `disputes` with one sentence why.

## Output
Write `precision/{case}-graded.json` (this grid's directory) and nothing else:

```json
{"case": "...",
 "matched": {"config/run/index": "existing-issue-id", "...": "..."},
 "new_issues": [
   {"id": "{case}-N1", "title": "...", "members": ["config/run/index"],
    "grade": "REAL|MINOR|FALSE|PREEXISTING|UNSURE", "confidence": "high|medium|low",
    "why": "...", "evidence": ["path:line at head"], "known": null, "fail_justified": null}
 ],
 "disputes": [{"id": "existing-issue-id", "why": "..."}]}
```

Every new finding's `ref` appears exactly once, either as a key of `matched` or in one new issue's `members`. Check that with a short script before finishing.

Final message: number matched, number of new issues with their grade counts, and any disputes. Nothing else.
