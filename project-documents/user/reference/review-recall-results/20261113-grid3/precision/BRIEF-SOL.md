---
docType: reference
project: squadron
dateCreated: 20261114
dateUpdated: 20261114
status: draft
---

# Grading brief: new sol findings

Grade definitions, how to read code (read-only, at `head`), and strictness are exactly as in `../../20261112-grid2/precision/BRIEF.md` (paths relative to this file). Read it first. Handle your cases one at a time. Finding text only; no earlier grades for these findings.

## Per case
- Findings: `precision/{case}-findings-sol.json` (this grid dir). Case repo, base and head: `cases-b2.txt` here, or `../20261112-grid2/cases.txt` if the case is not in cases-b2.txt (`case repo base head`). Repos live at `/Users/manta/source/repos/manta/{repo}`.
- Known bugs: the case's section in `/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-cases.md` (Batch 2 entries match by fix commit; digits after `cf`/`te` are the fix commit's first six).
- Existing issues, all that exist: `../20261112-grid2/precision/{case}-graded.json` (ids `{case}-I#`), `precision/{case}-graded.json` here (its `new_issues`, ids `{case}-N#`; for batch 2 cases this is the whole file), `precision/{case}-graded-b2.json` (its `new_issues`, ids `{case}-M#`).
- Match each finding to an existing issue where it is the same defect at the same place. Group and grade the rest as new issues, ids `{case}-S1`, `{case}-S2`, ... If a finding matches an existing issue but you think that issue's grade is wrong, still match it, and add the issue id and your reasoning to `disputes`. Do not edit existing files.
- Set `known` to the bug id on a new issue that is a known bug.

## Output
Write only `precision/{case}-graded-sol.json`:
`{"case": "...", "matched": {"ref": "existing-id"}, "new_issues": [ {id, title, members, grade, confidence, why, evidence, known, fail_justified} ], "disputes": [ {"id": "...", "reason": "..."} ]}`

Every ref in the findings file appears exactly once (in `matched` or one new issue's `members`); check with a short script per case.

Final message: per case, matched count and new-issue grade counts, plus the dispute ids. Nothing else.
