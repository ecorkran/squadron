# Precision grading brief

You are grading code-review findings for whether they are true and worth a reviewer's time. You are not grading the reviewers' style. Several AI reviewers each reviewed the same diff three times; your input is every CONCERN or FAIL finding they produced for one case.

## Inputs
- Findings: `precision/{case}-findings.json` (in this grid directory). Each item has `ref` (`config/run/index`), `severity`, `title`, `location`, `description`.
- Case list: `cases.txt` here gives `case repo base head`. Repos live at `/Users/manta/source/repos/manta/{repo}`.
- Known bugs for the case: the case's section in `/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-cases.md`. Read that section first.

## How to read code
Read the code as it was at `head`, never the working tree: `git -C {repo} show {head}:{path}`, `git -C {repo} diff {base} {head} -- {path}`, `git -C {repo} grep -n {pattern} {head}`. Do not check out, stash, reset, or modify any repo. You may look at later history (`git -C {repo} log --oneline {head}..HEAD -- {path}`) as supporting evidence that something was later fixed, but a later change is not proof by itself.

## Steps
1. Group the findings into distinct issues. Two findings are the same issue when they describe the same defect at the same place, even if worded differently or rated differently. One finding belongs to exactly one issue.
2. For each issue, check the claim against the code at head and assign one grade:
   - `REAL`: the claim is correct and describes a defect in code added or changed in base..head that would cause wrong behavior, a crash, wrong data, a hang, a security hole, or a silent failure path that a competent reviewer should ask to have fixed before merge.
   - `MINOR`: the claim is true but low value: style, naming, comments or docs, a missing test for an already-correct path, speculative hardening against inputs that cannot arrive, or a performance point with no real effect.
   - `FALSE`: the claim is wrong. The code does not do what the finding says, the case is handled elsewhere, the cited line does not exist, or the failure cannot happen.
   - `PREEXISTING`: true, but the code was not added or changed in base..head.
   - `UNSURE`: you cannot settle it from the code. Say exactly what would settle it.
3. Be strict both ways. A plausible-sounding finding is not REAL until you have read the code that proves it. A finding is not FALSE because it is phrased badly; grade the substance.
4. If an issue is one of the case's known bugs (B1, B2, ...) or controls (C1, ...), set `known` to that id.
5. For issues with any FAIL member, set `fail_justified` to true if the defect would really block a merge, else false.

## Output
Write one JSON file, `precision/{case}-graded.json`, and nothing else in the repo:

```json
{"case": "...", "issues": [
  {"id": "{case}-I1", "title": "one plain sentence naming the defect",
   "members": ["config/run/index", "..."],
   "grade": "REAL|MINOR|FALSE|PREEXISTING|UNSURE",
   "confidence": "high|medium|low",
   "why": "two to four sentences: what the code at head actually does and why that gives this grade",
   "evidence": ["path:line at head", "..."],
   "known": null, "fail_justified": null}
]}
```

Every `ref` in the findings file must appear in exactly one issue's `members`. Before finishing, verify that with a short script and fix any gap.

Your final message: the number of issues, the count per grade, and the IDs of any issue you graded with low confidence. Nothing else.
