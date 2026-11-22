---
docType: reference
project: squadron
dateCreated: 20261122
dateUpdated: 20261122
status: draft
---

# Squadron code review on a public benchmark: results (2026-11-22)

What was measured, what it showed, and what was still running when this was written. Files and scripts: [README.md](README.md). The harness is Martian's Code Review Bench (commit `23a35d0`): 50 public PRs, 173 human-written golden comments, 139 of them bug-type (the "strict" profile). Its 50 PRs are the Greptile benchmark's PRs.

## How to read the numbers

- One run per entry. One judge model (Claude Sonnet 4.5 through OpenRouter). The harness's own tools were judged by the same model in its stored results.
- Recall is golden comments found. Precision counts every issue that matches no golden comment as a false flag, including real defects the annotators did not list.
- Entries are scored from finding titles only unless marked "full text". With full text the harness's extractor split each finding about three ways (145 findings became 424 issues).
- The same entry extracted and judged twice gave 424 and 421 issues and identical recall.
- These are measurements. None of the conclusions below is a Project Manager decision unless it says so.

## Reviews run

| Reviewer | Reviews | Cost | Median time | Findings per review (FAIL / CONCERN / NOTE) |
|---|---|---|---|---|
| haiku-xhigh | 50 | $6.15 ($0.12 each, plan) | 4 min | 1.2 / 5.8 / 3.4 |
| sol-r (OpenRouter) | 50 | $6.40 ($0.13 each) | 35 s | 1.4 / 1.5 / 0 |
| sol (Codex plan) | 43 | plan | 64 s | 1.2 / 1.7 / 0.1 |
| fable-high | 40 of 50 when written | $1.48 each (plan) | 2 min | 0.9 / 4.9 / 2.7 |

Sol was stopped at 43 to keep the Codex 5-hour window: about 30 reviews had used 65% of it and 10% of the week.

## Entries scored (strict profile)

| Entry | Recall | Precision | Hits | False flags |
|---|---|---|---|---|
| haiku-xhigh | 64.7% | 25.7% | 90 | 260 |
| haiku-xhigh, behavior-lane categories only | 60.4% | 37.0% | 84 | 143 |
| haiku-xhigh, lane + truth-only opus-high comb | 53.2% | 42.5% | 74 | 100 |
| sol-r | 43.9% | 43.0% | 61 | 81 |
| sol-r, full text | 49.6% | 19.6% | 69 | 283 |
| haiku-xhigh + sol-r | 66.2% | 21.7% | 92 | 332 |
| pair with NOTE findings | 72.7% | 17.2% | 101 | 485 |
| pair after luna-r comb | 61.2% | 29.8% | 85 | 200 |
| pair after luna-r comb, full text | 66.9% | 17.0% | 93 | 454 |
| pair after luna-r then opus-high (the shipped `haiku-solr-luna-opus`) | 43.9% | 36.7% | 61 | 105 |

Outside tools, same judge model, from the harness's stored results: augment 61.9% / 49.4%; copilot 61.9% / 31.4%; coderabbit 60.4% / 31.8%; cubic 59.7% / 52.9%; qodo-extended 58.3% / 53.6%; greptile 50.4% / 44.9%; bugbot 46.0% / 52.0%; devin 44.6% / 66.0%; claude-code 42.4% / 34.3%.

"Behavior-lane categories" are the reviewer's own finding categories `correctness`, `security-hygiene`, `error-handling-observability`, `consistency-rot` and `type-contract-debt`. The rest (`test-debt`, `architectural-decay`, `performance-resource`, `documentation-drift`, `dependency-config-debt`, `other`) held 120 of haiku-xhigh's 260 false flags and 5 of its 90 hits.

## By golden-comment severity

| Entry | Critical | High | Critical + High | Medium | Low |
|---|---|---|---|---|---|
| haiku-xhigh | 11/12 | 41/54 | 52/66 (79%) | 34/55 | 4/18 |
| haiku-xhigh, behavior lane | 11/12 | 38/54 | 49/66 (74%) | 31/55 | 4/18 |
| lane + truth-only opus comb | 9/12 | 33/54 | 42/66 (64%) | 28/55 | 4/18 |
| pair after luna-r | 10/12 | 41/54 | 51/66 (77%) | 30/55 | 4/18 |
| shipped recipe (luna-r then opus-high) | 6/12 | 31/54 | 37/66 (56%) | 20/55 | 4/18 |
| sol-r | 8/12 | 32/54 | 40/66 (61%) | 20/55 | 1/18 |
| augment (best outside) | 7/12 | 39/54 | 46/66 (70%) | 33/55 | 7/18 |
| copilot | 9/12 | 35/54 | 44/66 (67%) | 35/55 | 7/18 |
| qodo-extended, cubic, coderabbit | 8-9 | 33-34 | 42/66 (64%) | 32-34 | 7-9 |

## What the error analysis showed

Scripts `e1.py` to `e5.py`.

- **haiku-xhigh leads on severe defects and trails on small ones.** Of its 49 misses, 14 were found by nine or more of the 21 tools: a wrong variable, a function returning the unmodified value, a bad CSS property, a test calling PUT on a DELETE route. It reads deeply (28 tool calls a review) and skips the line-by-line read.
- **sol-r adds little to haiku-xhigh.** In the pair it adds 2 hits and 72 false flags, and finds 3 of haiku-xhigh's 49 misses.
- **The opus-high comb drops true findings for being unimportant.** It dropped 29 of the 85 real hits luna-r had kept, 5 of them critical. In 28 of the 29 its reason agreed the claim was true and called it unlikely or minor. The comb prompt asks which findings "should be fixed before merge".
- **A truth-only comb prompt** (`comb-truth.yaml`: keep any true behavior defect, never drop for likelihood or impact) dropped 10, all as disputes of fact with the key. Who is right in those 10 is not known without running the code.
- **A precision ceiling.** After opus-high verified each one against the code, 100 findings remain that match no golden comment. The key has 2.8 bug-type items per PR; haiku-xhigh raises 4.6 behavior-lane findings and opus-high confirms 3.5.
- **NOTE findings hold real hits:** 9 more of the 139, with 153 more false flags.
- **Finding descriptions hold second defects:** full text finds 8 more than titles, with 254 more false flags.

## Greptile's own benchmark

Greptile names one bug per PR. Matching those 50 to the judged golden comments, with hand corrections in [greptile_overrides.md](greptile_overrides.md): haiku-xhigh 30 of 50 (60%), the shipped recipe 20. Greptile's page gives Greptile 41, Bugbot 29, Copilot 26, CodeRabbit 22, by its own rule (a person reading for a line-level comment). On the independent scoring above Greptile has 50% recall.

## Costs

- Judge: about one cent per issue judged. OpenRouter spend on judging so far about $55.
- luna-r comb: $0.50 for 143 calls. opus-high comb: $14.81 (plan) for 100 calls after luna-r; $9.49 for the truth-only run on 230 findings.

## Decided (Project Manager, 2026-11-22)

- Stop shipping the recipes that end in an opus-high comb. Issue #389.
- Do not drop real findings to raise a benchmark's precision.

## Running or not yet scored when this was written

| Item | State | To score |
|---|---|---|
| fable-high reviews | 40 of 50 | `convert.py ... sq-fable-t fable-high - CONCERN,FAIL title`, then `judge.sh` |
| haiku-xhigh second run (`RUN=2`) | started | reviewer spec `haiku-xhigh:2`; also the union `haiku-xhigh,haiku-xhigh:2` |
| haiku-xhigh with `rules-behavior-v2.md` (label `haiku-xhigh-v2`) | started | as above with the label |
| plain haiku, no tools, `rules-line-pass.md` (label `haiku-line`) | queued behind the two above | as above; also its union with haiku-xhigh |
| truth-only check by sol-r (`comb/truth-sol-r`) | done, not analysed | compare kept sets of opus-high, sol-r and fable-high against the judged hits: does the share of real findings rise with the number of verifiers that confirm one |
| truth-only check by fable-high (`comb/truth-fable-high`) | starts when the fable reviews finish | same |
| luna-r with the truth-only prompt (`comb/truth-luna-r`), entry `sq-pair-lunatruth-t` | running | decides whether the shipped comb prompt changes |
| Opus 4.5 and GPT-5.2 judges on the final entry | not started | `judge.sh` with `anthropic/claude-opus-4.5` and `openai/gpt-5.2` |
| Recipe fix #389 | edits in the working tree, not committed | review the diff, run format, lint, pyright and the touched tests, commit as `fix:` |

The harness checkout and the 50 sandboxes are in a scratch folder and can be rebuilt (`setup.py`, then clone the harness, add entries with `convert.py`). The judge results are copied to `harness-results/`; copy again after each judge run.

## Related results from the same day

- Stored-data re-cut of the 1,281 design reviews: scripts in `../20261122-recut/`.
- Four cheap reviewers on amoeba slice 260's task file: `../20261122-recut/amoeba260/` (`hits.json`). 7 of 17 key items, 8 with one borderline, for $1.73; six focused reviewers had found 10 for $4.21.
- Issues filed: #388 (reading floor), #389 (recipes).
