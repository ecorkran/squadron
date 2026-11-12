---
docType: reference
project: squadron
dateCreated: 20261112
dateUpdated: 20261112
status: draft
---

# Code Review Recall Runbook (real bugs)

How to measure whether a code reviewer finds bugs that were really in merged code. Reviewer configs (model, profile, prompt, effort) and outside tools (e.g. Greptile) are scored on the same cases.

Origin: #311. Thirteen runs on slice 307 showed that verdict, tool-call count and reasoning size do not predict whether a review finds a real bug. Only recall against known bugs does.

## How this differs from slice 427 (reviewer-recall)

- 427 plants mutations in real commits and checks each with a test. It runs without tools. It is deterministic and costs no LLM spend, but the defects are synthetic and it does not describe `sq review code` with tools.
- This runbook uses bugs that really shipped. It runs reviewers as they are used (tools on, real prompt). It is small, hand-labeled, and covers defects no test shows.
- The two are complementary. The status of 423-427 is a separate PM decision.

## Case record

One record per case, kept in this directory as `review-recall-cases.md` (add rows; do not rewrite history).

| Field | Meaning |
|---|---|
| id | `<repo>-<slice>` |
| repo, base, head | repo and the two commits; the review diff is `base..head` |
| bugs | list of ground-truth bugs, each with: id, one-line description, file and symbol, and the fix commit or issue that proves it was real |
| source | how the bug was found (later review, fix commit, issue) |
| notes | rules/CLAUDE.md in effect at `head`, anything that changes how to run it |

A bug counts only if a later commit or issue shows it was real. Do not add a bug from a reviewer's claim alone.

## Cases

1. **trading-data-307** (repo `manta-digital/trading-data`, base `dcfb86f1`, head `b5c3d781`)
   - Bug 1: the purchase script judged the whole `pass --estimate-only --json` payload as the plan summary. The plan is nested under `phases[purchase].summary`, so the first key lookup raised `KeyError`. Location: `scripts/cutover_304_checks.py` (`judge_estimate`).
   - Bug 2: the judge required verdict `allowed`, but `--estimate-only` reports `estimate_only` whenever there is something to buy, so the buy step was unreachable.
   - Proof: both fixed in `a7c5e36f` ("unwrap the purchase phase and accept estimate_only, answer second 307 review"). DeepSeek's FAIL review of `b5c3d781` is the archived finding (`project-documents/user/reviews/archive/307-review.code.futures-history-acquisition.md`).

## Finding more cases

Source of leads: a slice whose code was reviewed, merged, and then needed a `fix:` or a second round of review fixes for a bug the first review did not report. Search:

```bash
git log --format='%h %ad %s' --date=short | grep -iE "answer .*(second|2nd|another) .*review|fix: .*#[0-9]+"
```

For each candidate, in order:
1. Find the commit that introduced the bug (`git blame` on the fixed lines, or read the fix commit's own message).
2. Confirm the first review's saved findings did not already report it.
3. Write the record. Keep the case only if a person can state the bug in one sentence and point to the line.

Squadron's own history is a source too: issues closed by `fix:` commits where the bug came from a recent slice. Start there once trading-data has three or four cases. Aim for 8-12 cases before drawing conclusions from any comparison.

## Running a reviewer on a case

Use a scratch worktree so nothing in the real checkouts moves.

```bash
git -C <repo> fetch origin
git -C <repo> worktree add --detach <scratch>/<case> <head>
cd <scratch>/<case>
# provider keys: load the .env that holds them, in this shell only
set -a; . <squadron checkout>/.env; set +a
sq review code --diff <base> --model <alias> --no-save -v \
   --output file --output-path <scratch>/<run-id>.json
git -C <repo> worktree remove --force <scratch>/<case>
```

- Omit the slice number: the scratch worktree is not a registered cf project, and `--diff` scopes the review.
- Run each config at least 3 times per case. One run is noise: DeepSeek found both 307 bugs once and missed them in two later runs.
- The output file holds `tool_calls_made`, `reasoning_chars`, `profile`, `system_prompt_mode`, `setting_sources` and the findings. Keep all of it.
- For prompt or settings variants, patch a scratch checkout of squadron only. Never commit the knobs.

## Scoring

Per run, by a person (no model grades this):
- **Hit**: a finding that names the bug's file and symbol (or the same defect in the same function) and says what is wrong. An adjacent defect in the same function is not a hit; record it separately as "adjacent".
- **Precision**: label every other CONCERN or FAIL finding `real`, `style`, or `wrong`.

Report per config, over cases: recall (hits / bugs), runs with at least one hit, adjacent count, precision, median tool calls, cost per run. Always print n. Do not rank configs on fewer than 8 cases.

## Comparing outside review tools (Greptile and others)

Hosted tools review pull requests, so each case needs a PR with base and head. That means pushing branches to a repo the tool can read, which is outward-facing: the PM decides which repo (a scratch fork is the usual choice) and approves each push. Score the tool's comments with the same hit and precision rules. Record the tool's version, settings, and date, since they change.

## Known limits

- Reviewers here have `read_file`, `list_files` and `grep`. They cannot run the command whose output a script parses, and both 307 bugs came from output shape.
- Cases come from code that someone later had to fix. Bugs that were never noticed are not counted, so recall is an upper bound.
- Small sets: a difference of one hit is not a result.

## Results log

Append one dated line per batch: cases, configs, runs per config, recall, link to the saved outputs.

- 20261112: setup only. Thirteen runs on trading-data-307 (see #311): 0 of 13 found either bug. Outputs: `review-recall-results/20261112-311/` (A-F sdk sonnet knob variants, G deepseek, H sonnet via openrouter, I-K with the verification prompt). The verification prompt is the text appended in runs I-K: for every changed function that parses or judges another program's output, locate the producer in the repo, compare the emitted shape, key nesting and enumerated values with what the code reads, report mismatches, and say so if the producer is not found.
