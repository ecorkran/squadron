---
docType: reference
project: squadron
dateCreated: 20261113
dateUpdated: 20261113
status: draft
---

# Grading batch 2 brief

Two modes. Your prompt says which mode and which cases. Grade definitions, how to read code (read-only, at `head`), and strictness are exactly as in `../20261112-grid2/precision/BRIEF.md` (paths relative to this grid directory); read it first. Handle your cases one at a time.

## Mode NEW (cases never graded before)
- Findings: `precision/{case}-findings.json`. Case repo, base and head: `cases-b2.txt` (`case repo base head`). The case's one known bug: its entry under "Batch 2" in `/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-cases.md` (match the entry by fix commit; the case id's digits after `cf`/`te` are the fix commit's first six).
- Group findings into distinct issues and grade them as the grid 2 brief says. Set `known` to `"B1"` on the issue that is the case's known bug, if any finding describes it.
- Write `precision/{case}-graded.json` in this schema: `{"case": "...", "matched": {}, "new_issues": [ {id, title, members, grade, confidence, why, evidence, known, fail_justified} ], "disputes": []}`. Issue ids `{case}-N1`, `{case}-N2`, ...

## Mode MORE (cases already graded)
- Findings: `precision/{case}-findings-b2.json`. Case repo, base and head: `../20261112-grid2/cases.txt`.
- Existing issues, both of these: `../20261112-grid2/precision/{case}-graded.json` (ids like `{case}-I3`) and `precision/{case}-graded.json` here (its `new_issues`, ids like `{case}-N2`).
- Match each finding to an existing issue where it is the same defect at the same place; group and grade the rest as new issues with ids `{case}-M1`, `{case}-M2`, ...
- Write `precision/{case}-graded-b2.json` in the same schema (`matched` maps ref to an existing id of either kind).

## Both modes
Every ref in the findings file appears exactly once (in `matched` or one issue's `members`); check with a short script per case. Write only the output files named above. Final message: per case, matched count and new-issue grade counts, plus any disputes. Nothing else.
