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
| fable-high | 50 | $1.43 each (plan) | 2 min | 0.9 / 4.9 / 2.7 |
| haiku-xhigh, second run | 50 | $6.25 (plan) | 4 min | 1.2 / 5.6 / 3.5 |
| haiku-xhigh with `rules-behavior-v2.md` | 50 | $6.24 (plan) | 4 min | 1.1 / 3.1 / 0.2 |
| plain haiku, no tools, `rules-line-pass.md` | 50 | $0.50 (plan) | 20 s | 0.5 / 2.1 / 1.0 |

Sol was stopped at 43 to keep the Codex 5-hour window: about 30 reviews had used 65% of it and 10% of the week.

## Entries scored (strict profile)

| Entry | Recall | Precision | Hits | False flags |
|---|---|---|---|---|
| haiku-xhigh | 64.7% | 25.7% | 90 | 260 |
| haiku-xhigh, behavior-lane categories only | 60.4% | 37.0% | 84 | 143 |
| haiku-xhigh, lane + truth-only opus-high comb | 53.2% | 42.5% | 74 | 100 |
| fable-high ($1.43 a review) | 64.0% | 27.5% | 89 | 235 |
| fable-high, behavior-lane categories only | 57.6% | 36.9% | 80 | 137 |
| sol-r | 43.9% | 43.0% | 61 | 81 |
| sol-r, full text | 49.6% | 19.6% | 69 | 283 |
| haiku-xhigh + sol-r | 66.2% | 21.7% | 92 | 332 |
| pair with NOTE findings | 72.7% | 17.2% | 101 | 485 |
| pair after luna-r comb | 61.2% | 29.8% | 85 | 200 |
| pair after luna-r comb, full text | 66.9% | 17.0% | 93 | 454 |
| pair after luna-r comb with the truth-only prompt (`comb-truth.yaml`) | 64.0% | 29.4% | 89 | 214 |
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

## Run-to-run spread (haiku-xhigh, two runs)

| Run | Recall | Precision | Critical | High | Critical + High | False flags |
|---|---|---|---|---|---|---|
| 1 | 64.7% | 25.7% | 11/12 | 41/54 | 52/66 (79%) | 260 |
| 2 | 59.7% | 23.8% | 7/12 | 40/54 | 47/66 (71%) | 266 |
| either run | 70.5% | | | | 55/66 (83%) | |

75 golden comments were found by both runs, 15 only by run 1 and 8 only by run 2. The 79% on critical and high in run 1 was the better of two runs; the two average 75%, against 70% for the best outside tool on its one stored run. Read every single-run row in this file with a spread of about five points of recall and four critical items.

## Reviewer prompt variants and the line pass

| Entry | $/review | Recall | Precision | Critical + High | Low | False flags |
|---|---|---|---|---|---|---|
| haiku-xhigh run 1, all findings | $0.12 | 64.7% | 25.7% | 52/66 | 4/18 | 260 |
| haiku-xhigh run 1, behavior-lane filter applied afterwards | $0.12 | 60.4% | 37.0% | 49/66 | 4/18 | 143 |
| haiku-xhigh with `rules-behavior-v2.md` (told to report behavior defects only, one per finding) | $0.12 | 53.2% | 37.6% | 43/66 | 5/18 | 123 |
| plain haiku, no tools, `rules-line-pass.md` (line-by-line read of the diff) | $0.01 | 41.7% | 47.5% | 32/66 | 5/18 | 64 |

Unions of separately judged entries (strict recall of 139):

| Set | $/review | Recall | False flags (sum) |
|---|---|---|---|
| run 1 + line pass | $0.13 | 72.7% (101) | 324 |
| run 1 + run 2 | $0.24 | 70.5% (98) | 526 |
| run 1 + fable-high | $1.55 | 72.7% (101) | 495 |
| new-rules run + line pass | $0.13 | 64.7% (90) | 187 |
| run 1 + run 2 + fable-high | $1.67 | 74.1% (103) | |
| run 1 behavior-lane filtered + line pass | $0.13 | 71.2% (99) | 207 |

The last row judged as one entry (`sq-haiku-line-lane-t`: both reviewers' findings, behavior-lane categories only, 343 titles):

| Entry | $/review | Recall | Precision | Critical | Critical + High | Low | False flags |
|---|---|---|---|---|---|---|---|
| haiku-xhigh run 1 + line pass, behavior-lane filter on both | $0.13 | 69.1% (96) | 33.4% | 11/12 | 55/66 | 6/18 | 191 |
| the same with run 2 of each reviewer (`sq-haiku-line-lane-2-t`, 313 titles) | $0.13 | 66.9% (93) | 34.8% | 8/12 | 52/66 | 7/18 | 174 |

- The pair repeats: 69.1% and 66.9% recall, 33.4% and 34.8% precision. haiku-xhigh alone gave 64.7% and 59.7% on the same two runs, so the pair is ahead of its own haiku-xhigh run both times, by 4 and 7 points of recall and 8 and 11 of precision. Critical items still swing with the haiku-xhigh run (11 and 8 of 12). 84 golden comments are found by both pair runs, 105 (75.5%) by either.

- Judged as one entry the pair holds up: 6 more hits than haiku-xhigh run 1 alone, 3 more critical or high, and 69 fewer false flags. The union row filters only haiku-xhigh's findings; the judged entry also filters the line pass's (113 of its 134 kept), so the two differ by more than the judge run.
- Telling the reviewer to leave out the rules categories gives the same precision as filtering those categories out afterwards, and ten fewer hits. One run each, so part of that gap may be run-to-run spread.
- The no-tools line pass costs a cent, takes 20 seconds, and has the best precision of any squadron entry. It adds 11 golden comments to run 1, as many as fable-high did for $1.43. It does not close the low-severity gap (5 of 18).
- The new-rules run plus the line pass reaches run 1's recall with 187 false flags in place of 260.

## What the error analysis showed

Scripts `e1.py` to `e5.py`.

- **haiku-xhigh leads on severe defects and trails on small ones.** Of its 49 misses, 14 were found by nine or more of the 21 tools: a wrong variable, a function returning the unmodified value, a bad CSS property, a test calling PUT on a DELETE route. It reads deeply (28 tool calls a review) and skips the line-by-line read.
- **sol-r adds little to haiku-xhigh.** In the pair it adds 2 hits and 72 false flags, and finds 3 of haiku-xhigh's 49 misses. Both numbers are right: 3 compares the two entries judged separately; 2 is the pair judged as one entry (92 hits against 90), which is a separate extraction and judge run and differs by one.
- **The opus-high comb drops true findings for being unimportant.** It dropped 29 of the 85 real hits luna-r had kept, 5 of them critical. In 28 of the 29 its reason agreed the claim was true and called it unlikely or minor. The comb prompt asks which findings "should be fixed before merge".
- **A truth-only comb prompt** (`comb-truth.yaml`: keep any true behavior defect, never drop for likelihood or impact) dropped 10, all as disputes of fact with the key. Who is right in those 10 is not known without running the code.
- **A precision ceiling.** After opus-high verified each one against the code, 100 findings remain that match no golden comment. The key has 2.8 bug-type items per PR; haiku-xhigh raises 4.6 behavior-lane findings and opus-high confirms 3.5.
- **NOTE findings hold real hits:** 9 more of the 139, with 153 more false flags.
- **Finding descriptions hold second defects:** full text finds 8 more than titles, with 254 more false flags.

## Three verifiers on the same findings (`e6.py`)

haiku-xhigh's 230 behavior-lane findings, each checked with the truth-only prompt by opus-high ($9.49, plan), sol-r ($3.04) and fable-high ($35.61, plan). Nothing dropped; the count of verifiers that kept a finding is a label.

| Kept by | Findings | Golden hits (strict) | of them critical or high | False flags | Share matching the key |
|---|---|---|---|---|---|
| 3 of 3 | 166 | 72 | 42 | 93 | 45% |
| 2 of 3 | 22 | 6 | 2 | 17 | 26% |
| 1 of 3 | 17 | 3 | 2 | 12 | 25% |
| 0 of 3 | 25 | 3 | 3 | 21 | 12% |

- Agreement orders the list (45% down to 12%) but does not separate it: 72% of the findings are confirmed by all three.
- 93 findings that match no golden comment were confirmed as true by three models from three families. That is the benchmark's precision ceiling for a reviewer that reads deeply.
- Dropping the 0-of-3 tier removes 21 false flags and 3 hits, all three critical or high by the key.

## Greptile's own benchmark

Greptile names one bug per PR. Matching those 50 to the judged golden comments, with hand corrections in [greptile_overrides.md](greptile_overrides.md): haiku-xhigh 30 of 50 (60%), the shipped recipe 20. Greptile's page gives Greptile 41, Bugbot 29, Copilot 26, CodeRabbit 22, by its own rule (a person reading for a line-level comment). On the independent scoring above Greptile has 50% recall.

## Costs

- Judge: about one cent per issue judged. OpenRouter spend on judging so far about $55.
- luna-r comb: $0.50 for 143 calls. opus-high comb: $14.81 (plan) for 100 calls after luna-r; $9.49 for the truth-only run on 230 findings.

## Decided (Project Manager, 2026-11-22)

- Stop shipping the recipes that end in an opus-high comb. Issue #389.
- Do not drop real findings to raise a benchmark's precision.

## State at the end of the day

Every review, comb and judge run started on 2026-11-22 finished and is in this file. Not done:

- Opus 4.5 and GPT-5.2 judges on a final entry (`judge.sh` with `anthropic/claude-opus-4.5` and `openai/gpt-5.2`). Every number here is from one judge model.
Done after that list was written: the pair judged as one entry, twice (table above), and the shipped comb prompt (`src/squadron/data/templates/comb.yaml`) now carries the truth-only wording (6778d02a; the recipe fix is 32089d9d; both #389).

The harness checkout and the 50 sandboxes are in `~/.config/squadron/martian-20261122/` (copied there from the session scratch folder so a reboot does not clear them) and can be rebuilt (`setup.py`, then clone the harness, add entries with `convert.py`). The judge results are copied to `harness-results/`; copy again after each judge run.

## Related results from the same day

- Stored-data re-cut of the 1,281 design reviews: scripts in `../20261122-recut/`.
- Four cheap reviewers on amoeba slice 260's task file: `../20261122-recut/amoeba260/` (`hits.json`). 7 of 17 key items, 8 with one borderline, for $1.73; six focused reviewers had found 10 for $4.21.
- Issues filed: #388 (reading floor), #389 (recipes).
