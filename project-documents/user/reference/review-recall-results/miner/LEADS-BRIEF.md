# Lead checking brief

You are deciding whether mined leads are real review-recall cases. A mined lead is a `fix:` commit whose fixed lines `git blame` back to commits inside a range that a saved code review covered. Mining over-reports: in earlier batches only about 13 of 34 leads were real. Most leads are not cases; rejecting them is the normal outcome.

## Inputs
- Your leads: `miner/batch{n}.json` in this directory. Each lead has `repo`, `fix`, `subject`, `introducers` (commits blamed for the fixed lines), `review` (saved review file path in the repo), `head` (the review's reviewedSha), `base` (parent of the earliest buggy commit).
- Repos: `/Users/manta/source/repos/manta/{repo}`.
- The validity rules and examples of accepted and dropped cases: `/Users/manta/source/repos/manta/squadron/project-documents/user/reference/review-recall-cases.md` (read "What counts as a bug", one or two case entries, and "Dropped").

## Rules (all must hold)
1. The fix corrects a defect: wrong behavior, a crash, wrong data, a hang, a security hole. A fix that adds a capability, a gate, an option, a check or a warning, follows a later spec or contract change, or only changes docs, tests or messages does not count.
2. The defective code is present at `head` and was added or changed inside `base..head`. Code that predates `base` does not count.
3. The saved review at `head` did not report it. If it did, the lead is a **control** (record it as such; controls are useful).
4. A person can state the bug in one sentence and point to the line.

## How to read
Read-only. Use `git -C {repo} show {fix}`, `git -C {repo} show {head}:{path}`, `git -C {repo} diff {base} {head} -- {path}`, `git -C {repo} log --format='%h %s' {base}..{head}`, and `git -C {repo} show {head}:{review}` (the review file as saved at head; if it is missing there, try the fix commit or HEAD). Never check out, stash, reset or edit a repo. Check that `base..head` is a reasonable review range (not hundreds of commits); if it is huge, say so.

## Output
Write `miner/batch{n}-checked.json`, a list with one entry per lead:

```json
{"repo": "...", "fix": "...", "verdict": "CASE|CONTROL|REJECT",
 "reason": "one or two sentences: why",
 "bug": "one sentence stating the defect (CASE/CONTROL only)",
 "location": "path and symbol at head (CASE/CONTROL only)",
 "base": "...", "head": "...", "range_commits": 0, "diff_files": 0,
 "review": "review file path", "review_verdict": "PASS|CONCERNS|FAIL as saved"}
```

Leads from the same review range that pass can share a case; note that in `reason`.

Final message: counts of CASE, CONTROL, REJECT, and the fix ids of each CASE and CONTROL. Nothing else.
