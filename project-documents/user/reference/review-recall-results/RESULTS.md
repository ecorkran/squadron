---
docType: reference
project: squadron
dateCreated: 20261113
dateUpdated: 20261114
status: draft
---

# Code review recall: consolidated results

Every results table and comparison from the review-recall benchmark, in one place. Method and how to run things: [review-recall-runbook.md](../review-recall-runbook.md). Cases: [review-recall-cases.md](../review-recall-cases.md). Newest batches go at the bottom of the relevant section here, not in the runbook.

## How to read the numbers

- **Known-bug recall** (and "known kept" for combs) is graded by the fix commits, so it does not depend on agent judgment. It is the column to trust most.
- **Precision and REAL/noise columns** are agent grades (REAL, MINOR, FALSE, PREEXISTING, UNSURE), checked by a person on only two findings so far. Treat them as first-pass.
- **Run counts:** one run per config unless a section says otherwise. A difference of one or two findings is noise.
- **Comb terms:** REAL kept = REAL findings the comb kept, out of all REAL. Noise dropped = non-REAL findings the comb dropped, out of all non-REAL. Precision after = REAL kept / all kept. Known kept = known bugs kept.
- **Cost bases:** `sub` = what the SDK reports on a Claude subscription (API-equivalent, not a charge). `Codex plan` = no per-call cost. `alias_pricing` = computed from our price table on OpenRouter calls (not billed).
- **Regenerate:** `20261113-comb/comb.py score` (comb tables), `20261113-grid3/precision/score.py` (grid 3 tables), `20261112-grid2/precision/report.py` (grid 2 precision).

## 1. Recall, grid 2 (10 cases, 14 known bugs, 3 runs per config)

Source: 30 runs with 14 bugs. Hits on trading-ui-103's latent bug (found by every config) are shown with and without it.

| Config | Bug-hits of 42 | Without u103 (of 39) | Runs with a hit (of 30) | Median tool calls | Cost/run | Time/run (median) | Verdicts |
|---|---|---|---|---|---|---|---|
| haiku-xhigh (sdk) | 16 | 13 | 14 | 34 | $0.62 sub | 368 s | 16 FAIL, 14 CONCERNS |
| sol (codex) | 12 | 9 | 12 | not counted | $0.02 | 97 s | 26 FAIL, 4 CONCERNS |
| sonnet-high (sdk) | 7 | 4 | 7 | 9.5 | $0.57 sub | 68 s | 27 CONCERNS, 2 FAIL, 1 PASS |
| deepseek4-flash | 6 | 3 | 6 | 38 | $0.13 | 720 s | 24 CONCERNS, 4 FAIL, 2 PASS |
| luna (codex) | 6 | 4 | 6 | not counted | $0.001 | 37 s | 29 CONCERNS, 1 FAIL |
| sonnet no-tools (sdk) | 5 | 2 | 5 | 0 | $0.50 sub | 43 s | 30 CONCERNS |
| sonnet (sdk) | 4 | 1 | 4 | 2 | $0.52 sub | 28 s | 28 CONCERNS, 2 PASS |

Notes:
- haiku-xhigh found both 307 bugs (the nested `phases` payload, and the `estimate_only` verdict 3 of 3) by reading the producer, the check the verification prompt asked for. It also found 921's blocking `mt-run` 3 of 3, and 921 B1 and a122 B2.
- sol was second: 921's blocking `mt-run` 3 of 3 and squadron-932's early dispatch end 3 of 3. luna found amoeba-122 B2 and the 921 seed floor once each.
- Nobody found 175's running-total cost, 188's inclusive candle window, 197's merged-slice check, or amoeba-122's `-p slice=N` argv (0 of 21 runs each).
- Sonnet with no tools found almost as much as sonnet with tools (5 vs 4).
- sol and haiku-xhigh issue FAIL often (26 and 16 of 30). High recall with many FAILs is not yet shown to be better.

## 2. Precision, grid 2 (560 CONCERN/FAIL findings, 221 distinct issues, agent grades)

Grades: `review-recall-results/20261112-grid2/precision/BRIEF.md`. Human check file: `precision/REVIEW.md` (not yet done).

| Config | Findings | REAL | MINOR | FALSE | Precision | REAL per run | FAIL justified |
|---|---|---|---|---|---|---|---|
| haiku-xhigh | 235 | 57 | 166 | 2 | 24% | 1.9 | 13 of 23 |
| sol | 91 | 72 | 18 | 0 | 79% | 2.4 | 30 of 50 |
| sonnet-high | 128 | 24 | 103 | 1 | 19% | 0.8 | 2 of 3 |
| sonnet | 106 | 13 | 87 | 4 | 12% | 0.4 | 0 of 0 |

Notes:
- Almost nothing is FALSE (7 of 560). The noise is MINOR: true but low value.
- sol has the fewest findings and the most REAL ones. It found 41 REAL issues in total, 14 of them alone.
- Spot checks by me against the code: 227-I12 (fixed later in `94beba1b`) and 175-I19. Both held.

## 3. Grid 3, original 10 cases, run 1 (14 known bugs)

Precision is agent-graded; known bugs are fix-commit graded. Cost column is per review; basis in the last column.

| Config | Findings | Precision | Distinct REAL | Known bugs hit | Cost/review | Basis |
|---|---|---|---|---|---|---|
| haiku-xhigh | 73 | 26% | 19 | 6 | $0.53 | sub |
| sol (codex) | 31 | 81% | 25 | 5 | n/a | Codex plan |
| **sol-r** | **32** | **53%** | **17** | **3** | **$0.24** | alias_pricing |
| sol-high (codex) | 32 | 75% | 24 | 2 | n/a | Codex plan |
| hy4 | 66 | 20% | 13 | 4 | $0.35 | alias_pricing |
| luna-r-high | 31 | 42% | 13 | 3 | $0.04 | alias_pricing |
| luna-r-xhigh | 32 | 34% | 11 | 3 | $0.06 | alias_pricing |
| minimax31-flash | 56 | 14% | 7 | 2 | $0.06 | alias_pricing |
| sonnet-high | 38 | 16% | 6 | 2 | $0.52 | sub |
| luna-xhigh (codex) | 15 | 33% | 5 | 2 | n/a | Codex plan |
| deepseek4-flash | 24 | 38% | 9 | 1 | $0.12 | alias_pricing |
| sonnet | 39 | 10% | 4 | 1 | $0.50 | sub |
| sol-xhigh (codex) | 4 | 100% | 4 | 1 | n/a | Codex plan |

Notes:
- sol-r (OpenRouter, same model as Codex sol) came in well below Codex sol on this run: 53% vs 81% precision, 3 vs 5 known bugs. One run; provenance or effort may explain it, not checked.
- luna at xhigh is not haiku-xhigh (3 vs 6 known bugs in grid 2). luna-r-high beats luna-r-xhigh. Effort high did not help sol (2 vs 5 known).
- sol-xhigh has one review (307, run 1). Too few to rank.
- minimax31-flash has the highest FALSE rate: 21% of its findings.
- The cost column is recomputed from saved outputs for rows marked alias_pricing, and from the earlier notes for sub rows.

## 4. Grid 3, new 7 cases, run 1 (7 known bugs)

Context-forge and trading-engine cases. sol and sol-high now cover all 7 cases (graded 2026-11-14, section 13); luna and luna-xhigh are still partial.

| Config | Cases with findings | Findings | Precision | Distinct REAL | Known bugs hit |
|---|---|---|---|---|---|
| sol (codex) | 7 | 15 | 53% | 8 | 2 |
| minimax31-flash | 7 | 24 | 29% | 7 | 2 |
| haiku-xhigh | 7 | 31 | 19% | 6 | 2 |
| sol-high (codex) | 7 | 15 | 53% | 8 | 1 |
| hy4 | 7 | 33 | 24% | 7 | 1 |
| sonnet-high | 7 | 16 | 12% | 2 | 1 |
| luna (codex) | 1 | 1 | 100% | 1 | 1 |
| luna-r-xhigh | 6 | 11 | 36% | 4 | 0 |
| luna-r-high | 6 | 10 | 40% | 4 | 0 |
| luna-r | 6 | 6 | 50% | 3 | 0 |
| luna-xhigh (codex) | 3 | 3 | 67% | 2 | 0 |
| qwen38-27b | 5 | 7 | 14% | 1 | 0 |
| sonnet | 5 | 14 | 0% | 0 | 0 |

5 of 7 known bugs were found by someone. sol found context-forge-e984cea3's fence bug, and the sol family got a partial hit on cf5e840c B1, counted (see section 13). qwen38-27b finds about one finding per review and is weak as a reviewer.

## 5. Comb test (run 1 of 4 reviewers, 40 reviews, 54 REAL, 14 known bugs)

A comb reads one finished review's CONCERN/FAIL findings plus the code at head and marks each KEEP or DROP. Prompt and harness: section 9. Inputs: haiku-xhigh, sol, sonnet-high and sonnet on all 10 original cases.

Aggregated over all four reviewers:

| Comb | Calls | REAL kept | Noise dropped | Precision after | Known kept | Cost | Mean s/call |
|---|---|---|---|---|---|---|---|
| opus-high | 40 | 49/54 (91%) | 118/127 (93%) | 49/58 (84%) | 14/14 | $10.45 sub | 38 |
| luna-r | 40 | 54/54 (100%) | 86/127 (68%) | 54/95 (57%) | 14/14 | $0.22 | 36 |
| luna-r-high | 40 | 54/54 (100%) | 84/127 (66%) | 54/97 (56%) | 14/14 | $0.30 | 64 |
| opus-medium | 40 | 47/54 (87%) | 116/127 (91%) | 47/58 (81%) | 13/14 | $11.72 sub | 30 |
| qwen38-27b | 40 | 51/54 (94%) | 106/127 (83%) | 51/72 (71%) | 13/14 | $5.94 | 351 |
| haiku-xhigh | 40 | 52/54 (96%) | 100/127 (79%) | 52/79 (66%) | 12/14 | $1.01 sub | 72 |
| terra-r | 40 | 51/54 (94%) | 106/127 (83%) | 51/72 (71%) | 11/14 | $1.96 | 21 |
| sol-r | 40 | 50/54 (93%) | 109/127 (86%) | 50/68 (74%) | 11/14 | $3.01 | 20 |
| sol | 40 | 50/54 (93%) | 114/127 (90%) | 50/63 (79%) | 10/14 | Codex plan | 40 |
| sol-high | 40 | 49/54 (91%) | 110/127 (87%) | 49/66 (74%) | 10/14 | Codex plan | 49 |
| sonnet-high | 40 | 40/54 (74%) | 120/127 (94%) | 40/47 (85%) | 8/14 | $6.74 sub | 29 |
| luna-r+opus-high (two-stage) | 40 | 47/54 (87%) | 121/127 (95%) | 47/53 (89%) | 12/14 | see note | 35 |

Notes:
- The two-stage row's cost ($28.96) is higher than opus-high alone ($10.45) on fewer findings. Not explained; do not use it until checked.
- Mean s/call is the mean over calls, not the median the earlier table used.
- Codex rows have no per-call cost.
- Only opus-high is both safe (all known bugs kept) and clean. luna is safe and nearly free but keeps a third of the noise.
- sonnet-high, the usual interactive comb, drops a quarter of the real issues and 6 of 14 known bugs.
- The sol family drops known bugs on both Codex and OpenRouter, so it is the model, not the harness.
- Effort high did not help sol or luna as a comb.

Per reviewer: each cell is kept findings, precision after, known bugs kept.

| Comb | haiku-xhigh (raw 73, 19 REAL, 26%, 6 known) | sol (raw 31, 25 REAL, 81%, 5 known) | sonnet-high (raw 38, 6 REAL, 16%, 2 known) | sonnet (raw 39, 4 REAL, 10%, 1 known) |
|---|---|---|---|---|
| haiku-xhigh | 32, 56%, 5 | 26, 92%, 4 | 12, 50%, 2 | 9, 44%, 1 |
| luna-r | 36, 53%, 6 | 29, 86%, 5 | 17, 35%, 2 | 13, 31%, 1 |
| luna-r+opus-high | 20, 85%, 5 | 23, 96%, 4 | 7, 71%, 2 | 3, 100%, 1 |
| luna-r-high | 37, 51%, 6 | 30, 83%, 5 | 16, 38%, 2 | 14, 29%, 1 |
| opus-high | 21, 86%, 6 | 24, 92%, 5 | 10, 60%, 2 | 3, 100%, 1 |
| opus-medium | 20, 80%, 6 | 23, 96%, 5 | 9, 56%, 1 | 6, 67%, 1 |
| qwen38-27b | 25, 76%, 6 | 28, 86%, 4 | 12, 42%, 2 | 7, 43%, 1 |
| sol | 22, 73%, 3 | 27, 93%, 5 | 7, 71%, 1 | 7, 57%, 1 |
| sol-high | 23, 65%, 3 | 28, 89%, 5 | 7, 71%, 1 | 8, 50%, 1 |
| sol-r | 24, 67%, 4 | 28, 89%, 5 | 7, 71%, 1 | 9, 44%, 1 |
| sonnet-high | 19, 79%, 5 | 20, 100%, 3 | 4, 75%, 0 | 4, 50%, 0 |
| terra-r | 26, 65%, 4 | 27, 93%, 5 | 10, 50%, 1 | 9, 44%, 1 |

Best pipeline so far (both single runs): haiku-xhigh review, then opus-high comb: 73 findings at 26% become 21 at 86%, all 6 known bugs kept. Two-stage luna-r then opus-high: 89% precision, 12 of 14 known.

## 6. Qwen38-27b as a comb, detail

- 40 of 40 reviews. One call (188, sonnet-high) hit an upstream idle timeout and was rerun.
- Mean seconds per call: 275 to 439 across the four reviewers, against 17 to 92 for the other combs.
- Its reviews came through the squadron review recovery path on every call (section 9); decisions come from the first reply.

## 7. Costs and time, summary

- SDK (`sub`) figures are what the SDK reports on a subscription. They are not charges.
- OpenRouter figures are from our price table. OpenRouter balance and the monthly key cap are in section 10.
- Codex figures are plan-based. A Codex ChatGPT window covered about 37 reviews before "workspace out of credits".
- Seven haiku-xhigh reviews moved the Claude 5-hour meter about one point. The long interactive session was the largest Claude cost.
- Grading cost: batch 1 (one agent per case, 135 findings) about 840k agent tokens, about 6k per finding. Batch 2 (5 agents, about 285 findings) about 660k, about 2.3k per finding.
- OpenRouter cache hits were 81 to 89% already. Output and reasoning are about 64% of cost.
- Batch variants (about 50% off, asynchronous up to 24 hours) fit single-shot jobs only: no-tools reviews, combs with code pasted in, grading. Tool-using reviews do not fit. Squadron has no batch support.

## 8. Known limits

- Precision is agent-graded. Two findings have been checked by hand.
- One run per config for most rows. Runs 2 and 3 exist only for grid 2 precision and the grid 3 original cases in part.
- The comb test uses run 1 of each reviewer.
- Codex rows are incomplete except the sol family (runs 1 to 3, section 13); luna Codex rows are partial. Codex credits ran out.
- Squadron's review recovery misfires on comb output (section 9). The fix is uncommitted.
- Two costs do not add up and are unexplained: the two-stage comb row above, and the ~$0.03 vs $0.04 difference for luna-r-high between the earlier notes and the recomputed cost.

## 9. The comb prompt

- **File:** `review-recall-results/20261113-comb/comb.yaml`. Committed once in `9bc108a6`.
- **What it asks:** for each finding, read the code it cites and answer KEEP or DROP. KEEP only if the claim is correct and describes a defect in changed code that would cause wrong behavior, a crash, wrong data, a hang, a security hole or a silent failure path, and should be fixed before merge. DROP for everything else: wrong claims, style, naming, docs, hardening against inputs that cannot arrive, performance points with no real effect, and code the change did not touch.
- **Output:** one line per finding, `<finding-id>: KEEP|DROP — reason`. Read-only tools: read_file, list_files, grep.
- **Status:** a first version written in this session. It has one committed revision and no tuning, and it has not been compared against any other prompt.
- **Not your interactive comb prompt.** I could not find your interactive comb prompt anywhere in the repo or in your skills and commands. If it exists somewhere, the two should be diffed.
- **Uncommitted changes today:**
  - `comb.yaml` sets `output: decisions`.
  - `comb.py` gives any finding with no verdict an explicit DROP with the reason "no verdict from comb; default DROP". No existing output hit this path.
  - Squadron: a template `output` field. `decisions` skips the review recovery turn, which otherwise ran on every comb call (recovery turn used in 40 of 40 for most configs). Review templates default to `review` and are unchanged. Tests pass in `tests/review`, 1341 passed and 2 skipped. Pyright shows 16 errors in the touched test files, all on lines not written in this change.
- **Not yet verified:** that the first-verdict-wins rule means the recovery turn never changed a decision. I have not diffed turn one against turn two.

## 10. Open items

- Grid 3 original cases: runs 2 and 3 for the configs in section 3, except the sol family (graded, section 13). The grading step needs an agent, so pass several cases per agent.
- Codex runs when a window is fresh. Most of `jobs-codex.txt` is unfinished.
- Qwen as a reviewer is weak. Qwen as a comb is credible on haiku's output (6 of 6 known bugs kept) but slow.
- Check the two-stage cost row before quoting it.
- Human check of grid 2 grades: `precision/REVIEW.md`, REAL and FALSE first.
- Push decision. Nothing is pushed; `main` is about 20 commits ahead.
- Raise the monthly cap on the OpenRouter key before the expensive screen (about $54 left of $100 at last check).

## 11. Grader check, 30-item sample (2026-11-14)

**Sample:** 30 issues from the grid 2 precision pass, stratified (REAL 12, MINOR 6, FALSE 7, PREEXISTING 3, UNSURE 2). Not a random sample. Regrades were Sonnet at medium and high effort, given the finding text only, with no earlier grade.

**Agreement:**
- Sonnet high matches the original grades on 25 of 30. Sonnet medium matches on 21 of 30.
- The two regrades agree with each other on 23 of 30.
- Ten items split the graders. Of those, code settles six and four are judgement calls (225-I4, 225-I1, 175-I3, 197-I15).

**Decision errors, from checking the code:**
- Sonnet medium read the tick universe as one product (225-I1 graded MINOR). It also got four settled items wrong: 197-I19, 197-I22, 188-I13, u103-I3.
- Sonnet high matched every settled answer it covered.
- The sorting agent called 197-I15 new code, but the call already existed in base. It also framed 175-I24 as a missing-test point, when the claim is a misroute that doesn't happen.
- 175-I3 is PREEXISTING: the test predates the change and the diff doesn't touch its assertions.

**Human labels so far** (judgement items plus a few settled ones): 175-I17 MINOR, 175-I24 FALSE, 197-I19 REAL, 225-I1 REAL, 225-I4 REAL. 175-I17 is contested: the sorting agent called it REAL because a hand-edited file can reach it.

**Not an accuracy measure.** The ten disputed items were chosen for disagreement, so they can't give overall grader accuracy. Scoring them would show how graders handle contested cases.

**Next, for an accuracy comparison:** a random sample across all graded items, with code-settled answers where the code decides. Compare Sonnet high against Opus and others. Opus needs your go-ahead.

## 12. Random batches of graded issues (2026-11-13)

**Method:** four seeded random batches of ten issues, drawn from the 221 grid 2 graded issues without replacement. Each batch went to one Sonnet high agent with the finding text only, no earlier grade. The agent settled an item from the code and the base-to-head diff, or escalated it. Each batch used about 130k to 150k subagent tokens, roughly 1% of the session meter.

**Settled items:** 33 of 40. Of those, 30 match the original pass.
- Batch 1: 8 of 10 agree. 175-I17 and 921-I9 differ.
- Batch 2: 6 of 6 agree.
- Batch 3: 8 of 9 agree. 197-I15 differs.
- Batch 4: 8 of 8 agree.

**Escalations resolved:** 197-I1 agrees with the original (REAL). 227-I5 agrees (MINOR). a122-I13 differs: the sorter says MINOR, because `journal_issue` refuses an entry without a `run_id`, so the claimed crash can't happen; the original said REAL.

**Still open, with the grades that depend on them:**
- **197-I15, ruled REAL:** a changed line with a pre-existing defect is REAL, because the change touched it. The original PREEXISTING grade is wrong under this rule.
- **307-I1, ruled REAL:** a defect in a new mode is REAL, even when it repeats an existing mismatch. PREEXISTING applies only to code the change neither added nor touched.
- **197-I14, decided:** plain `sq run --resume` after a halted batch is not a supported recovery. Item resume is the recovery. Graded MINOR: the state problem is real, but it only shows on a path nobody should use.
- **921-I5, decided:** the cutover runs unattended. The repair runs as `manta-trading` via `sudo -u`, not root. Graded REAL. Needs a narrow sudoers alias on the host and in trading-data before the cutover.
- **225-I11:** the config says mypy, and CI runs no type checker. Whether the original FALSE holds still needs a mypy run.
- **921-I9, decided:** REAL. The freshness probe compares the refresh's finish time with the newest bar's `created_at`, so a bar written during a refresh can read as fresh when the refresh never saw it. Every mass check read is a minimum, so the result is a wrong FAIL, not a false PASS. Fix: compare against the refresh's start time (`last_run_started_at`). Original MINOR grade left in the data; this adjudication overrides it.

**Batches 5 and 6 (added 2026-11-13):** two more seeded batches of ten, same method (Sonnet high, finding text only, no earlier grade). All 20 settled, none escalated. 19 agree with the original pass. The one disagreement is 307-I4: the original says REAL, the sorter says MINOR (loose attribution in a failure message; the failure itself fires correctly). Decided REAL: the over-session listing is wrong data, not a message. Subagent cost: batch 5 115,688 tokens, batch 6 122,632. Across all six batches: 53 settled, 49 agree (92%). **Opus, same 60 items** (batches 1–6, same brief, no earlier grades): 60 of 60 settled. Opus agrees with the original on 56 of 60 (93%). Opus and Sonnet high agree on 49 of 53 items both settled. Opus disagrees with the original on 921-I9 (Opus REAL), a122-I13 (Opus MINOR), a122-I15 (Opus REAL), and 197-I14 (Opus REAL, against the decision above).

**Decided since:** 197-I14 (plain resume after a halt is not a supported recovery; graded MINOR, `197-graded.json` updated). 225-I11 checked: `mypy` passes on `status_reads.py` at head, and the project has no pyright config, so the original FALSE holds.

## 13. Sol family, all runs (2026-11-14)

**Method:** 160 CONCERN/FAIL findings from `sol`, `sol-high` and `sol-xhigh` reviews that no earlier grading covered (runs 2 and 3 of the original cases, plus all runs of the 7 new cases). Six Sonnet agents (about 540k subagent tokens in all), finding text only, each matching findings to existing issues or grading new ones. Brief: `20261113-grid3/precision/BRIEF-SOL.md`. Output: `precision/{case}-graded-sol.json`. Table: `20261113-grid3/precision/score.py`. Agent grades, not hand-checked.

**Result:** 136 of 160 findings matched issues already graded. 24 findings fell into 11 new issues: 3 REAL, 6 MINOR, 1 PREEXISTING, 1 FALSE. Repeat runs found almost nothing new.

All runs, per config:

| Config | Case set | Reviews | Findings | REAL | MINOR | FALSE | PREEXISTING | Precision | Distinct REAL | Known bugs hit |
|---|---|---|---|---|---|---|---|---|---|---|
| sol | original (14 known) | 30 | 91 | 72 | 18 | 0 | 1 | 79% | 31 | 5 |
| sol-high | original (14 known) | 30 | 100 | 73 | 25 | 2 | 0 | 73% | 33 | 4 |
| sol-xhigh | original (14 known) | 1 | 4 | 4 | 0 | 0 | 0 | 100% | 4 | 1 |
| sol | new (7 known) | 21 | 46 | 25 | 17 | 0 | 4 | 54% | 10 | 3 |
| sol-high | new (7 known) | 21 | 50 | 27 | 19 | 0 | 4 | 54% | 11 | 3 |

Notes:
- sol finds the same 5 known bugs on the original cases in run 1 and across all 3 runs. sol-high goes from 2 (run 1) to 4 across 3 runs, so repeats help sol-high and not sol.
- Precision on the new cases (54%) is well below the original cases (73 to 79%). Four PREEXISTING findings per config on the new cases, at most one on the original.
- Known bugs on the new cases: both configs hit 3 of 7 (cf5e840c B1 partial, below), including context-forge-e984cea3 (fence detection; sol 3 of 3 runs, sol-high 2 of 3) and cfe9597a B1. Both miss cfafd8f7 B1 (`gateByReadiness` throw) and teccae5e B1.
- cf5e840c B1 (state persisted `in_progress` before `renderFacts` throws): partial hit, **counted** (PM decision 2026-11-14, may be tightened later). sol runs 2 and 3 and sol-high run 1 point at the exact lines and say the failure comes after state was persisted, but propose only wrapping the error in `AdoptionError`, which leaves `in_progress` on disk. Graded as `cf5e840c-S2` (REAL, low confidence, known B1). The other N2 findings from other configs are about malformed TOML or guide reads and are not hits.
- New REAL issues: cfe984ce-S1 (the fence bug, known), cf5e840c-S2 (the counted partial B1 hit) and 307-S1 (stale stored dataset edge refuses the cutover with a misleading message; low confidence, not verified).
- sol-xhigh is one review. Not ranked.
