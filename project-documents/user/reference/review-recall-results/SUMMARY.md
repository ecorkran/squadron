---
docType: reference
project: squadron
dateCreated: 20261117
dateUpdated: 20261123
status: draft
---

# Model benchmark: what we measured and what it says

The short version of [RESULTS.md](RESULTS.md) (23 sections of tables) for a person. The same answers in a form an agent can look up: [ANSWERS.yaml](ANSWERS.yaml). Where the two disagree, RESULTS.md and the data files are the source.

## What was measured

| Experiment | Cases | Reviews or drafts | Where |
|---|---|---|---|
| Code review recall and precision | 10 real merged diffs, 14 known bugs (7 more cases, 7 known bugs, run 1) | 13 configs, mostly one run each; 3 runs for grid 2 | RESULTS 1-4, 13 |
| Combs on code reviews | the same 10 cases, 4 reviewers | 480 comb calls, 12 comb models | RESULTS 5-6 |
| Design review, first pass | 9 cases (slice designs and one task breakdown), 25 flaws | 36 reviews | RESULTS 14 |
| Design review, 3 runs | the same 9 cases | 162 reviews, 6 configs | RESULTS 15 |
| Design review on mined cases | 43 cases (19 arch, 32 slice, 31 task flaws; 82 flaws in all) from squadron, context-forge and migratory history | 258 + 344 + 43 reviews, up to 7 configs | RESULTS 16-17 |
| Writers | 5 design slices, 4 task slices | 4 writers per slice, opus-high judging both orders | RESULTS 17 |
| Comb on design reviews | the 43 mined cases, haiku-xhigh reviews | 129 comb calls | RESULTS 18 |
| Cheap OpenRouter design reviewers | the 43 mined cases | glm52, glm-flash, deepseek4-flash, minimax, one run each | RESULTS 19 |
| More cheap and mid-price design reviewers | the 43 mined cases; a 15-case subset for the dearer models | mimo, hy4, minimax31-flash, qwen38 family, luna-r-high on 43; glm53, kimi3, terra and sol on 15 | RESULTS 20 |
| Code review on a public benchmark (2026-11-22) | Martian Code Review Bench: 50 public PRs, 139 bug-type golden comments | 7 reviewer runs of 50 (haiku-xhigh twice, fable-high, sol-r, line pass twice, a rules variant), combs, three verifiers; one outside judge model | RESULTS 21 |
| Re-cut of the stored data (2026-11-22) | the 1,281 graded design reviews and the grid 2 code grades | no new reviews | RESULTS 22 |
| Document reviews on the current templates (2026-11-22) | the 43 mined cases | 258 new reviews (haiku-xhigh and sonnet-high twice, opus-high, fable-high) against the stored ones | RESULTS 23 |

A design flaw counts only if the document contradicts itself, its parent or the code, omits a success criterion, or has a task that cannot be done as written. Later decisions and scope changes never count. Flaws were mined from review history and checked against the text at that commit.

## Answers

Confidence is about the evidence, not the model.

| Question | Answer | Confidence |
|---|---|---|
| Best code review setup (2026-11-22) | haiku-xhigh plus a no-tools line pass, with only the behavior categories counted: 69.1% and 66.9% recall at 33.4% and 34.8% precision on the public benchmark, $0.13 a review. haiku-xhigh alone: 64.7% and 59.7% at 25.7% and 23.8%. fable-high alone: 64.0% at 27.5% for $1.43. Not built as a recipe yet (slice 437); the shipped default is haiku-xhigh alone. | Medium-high (two runs, one judge model, one benchmark) |
| Do the 2026-11-21 review templates matter | Yes, for slice designs and task files. Flaws that need the code found went from 13 to 27 and 24 of 35 (haiku-xhigh), 7 to 26 and 24 (sonnet-high), 9 to 26 (opus-high), 19 to 32 (fable-high). Document-only flaws did not move. Architecture reviews did not move. The document-review numbers below this row that predate 2026-11-22 are from the old templates. | High on the direction; the size rests on one stored run |
| Worst reviewer | On the old templates, Sonnet at any effort: about 40% recall against 47-57% for the other Claude configs, and last in the code grid. On the current templates sonnet-high is within a few flaws of haiku-xhigh on documents (57 and 54 of 82 against 62 and 57), because it now reads. It still barely reads architecture documents. Not rerun on code. | High for the old templates; medium for the new |
| Best design reviewer for the money | haiku-xhigh. Current templates: 62 and 57 of 82 flaws for $0.33 a review; fable-high 67 for $3.06, opus-high 64 for $1.25, sonnet-high 57 and 54 for $0.45. Old templates: $0.34 a review and a tie with the dearer configs (43.7 flaws per run, fable-medium 46.3, opus-high 42.7). | High on value; medium on who is top, because the run-to-run spread is 3-6 flaws |
| Cheap reviewers (OpenRouter) | minimax31-flash finds 43 of 82 for $0.04 a review (haiku-xhigh 44 for $0.24) and is best on slice designs (20 of 32). hy4 45 at $0.19; mimo 38, qwen38-flash 38 and glm-flash 37 at $0.06-0.07; hy4-flash 32 and mimo-flash 31 at about a cent. Not worth a slot: glm52, minimax (M3), qwen38-27b, luna-r-high. haiku-xhigh plus minimax31-flash find 58 of 82, as many as haiku-xhigh plus fable-medium. | Medium (one run; precision not measured) |
| Dearer and OpenAI reviewers | glm53 (6 of 22 on a 15-case subset, $0.40 a review), kimi3 (12), qwen38 (10), qwen38-max (13, $0.74), sol and terra (9 each), luna (2) do not beat the cheap models. | Low (22 flaws) |
| Design review against code review | haiku-xhigh leads both. The rest differs: sol (Codex) found 12 of 42 known bugs at 79% precision on code, and 2 of 25 flaws on design. | Medium (sol design: 9 cases, one run) |
| Combs | Code: on our own 10 cases the opus-high comb kept 91% of real findings and all known bugs. On the public benchmark it dropped 29 of 85 real hits, 5 of them critical, nearly all for being unlikely or minor, not for being false. Recipes that end in an opus-high comb are no longer shipped (PM, 2026-11-22, #389), and the shipped comb prompt now asks only whether a finding is true. Design: the opus-high comb keeps 78% of real findings, loses 7 of 58 distinct flaws, and costs three times the review. | Medium |
| Two reviewers | Code: haiku-xhigh plus the line pass is the pair that pays (row 1); sol-r adds 2 hits and 72 false flags to haiku-xhigh. Documents, current templates, of the 78 flaws a model saw: haiku-xhigh twice 68 ($0.66), haiku-xhigh plus sonnet-high 67 ($0.78), haiku-xhigh plus fable-high 72 ($3.39), fable-high alone 67 ($3.06). Old templates: fable-medium plus haiku-xhigh 66 of 82. | Medium |
| Best writer | Designs: fable-medium (14 wins, 2 losses, 3 ties), then opus-high. Tasks: opus-high or fable-medium. haiku-xhigh and sonnet-high write poor designs and lose to the original. | Medium for design; low for tasks (4 slices, thin fable sample) |
| Effort | Opus: high beats medium (42.7 against 38.7). Sonnet: no effect. Fable: high 52, medium 49 on one run, inside noise. | Medium for opus, low for fable |
| Hardest case kind | On the old templates, slice designs: 25 of 32 flaws found by anyone (arch 18 of 19, tasks 25 of 31). On the current templates slice designs are the best covered: one reviewer finds 25 to 30 of 32. Architecture is where the new templates changed nothing (10 to 15 of 19, as before). 4 of 78 flaws were found by none of the new reviews. | Medium |
| Does severity sort findings | No, on documents: 74-100% of real hits are labelled CONCERN or NOTE. On code, FAIL is 87% real for haiku-xhigh and CONCERN 17%. | Medium (stored data, agent grades) |
| Does agreement between verifiers filter findings | No. Three verifiers from three model families all kept 166 of haiku-xhigh's 230 behavior findings, 93 of which match no golden comment. Agreement ranks findings; it does not separate real from false. | Medium |

## Recipes worth keeping

Ideas that came out of the data, so they are not lost:

- **Code review: haiku-xhigh plus a no-tools line pass, behavior categories only (2026-11-22).** The line pass is plain haiku reading the changed lines of the diff for slips (`20261122-martian/rules-line-pass.md`): a cent and 20 seconds a review, and the best precision of any squadron entry (47.5%). It finds the small slips haiku-xhigh skips while reading deeply. The pair is slice 437.
- **Filter finding categories after the review; never tell the reviewer to leave categories out.** The categories outside behavior held 120 of haiku-xhigh's 260 false flags and 5 of its 90 hits. Telling the reviewer to omit them cost ten more hits for the same precision.
- **A comb should ask only whether a finding is true.** Asking what "should be fixed before merge" made opus-high drop true findings as minor.
- **Review templates that make the reviewer read:** the whole document in the prompt, criteria that say to open the code, and a per-section list of what was checked (#382). On documents this did more than any change of model.
- **Code review: haiku-xhigh and sol in parallel, then an opus-high comb. Withdrawn 2026-11-22 (#389).** On the 10 original cases (one run) the comb cut 57% of the findings and lost 3 of 33 real issues. On the public benchmark the same recipe fell to 43.9% recall, below haiku-xhigh alone.
- **Two-stage comb on code (luna-r, then opus-high):** 89% precision, 12 of 14 known bugs kept on the original cases. Ends in the opus-high comb, so the same withdrawal applies.
- **Design review: haiku-xhigh by default, no comb.** A second haiku-xhigh run is the cheapest step up on the current templates (68 of 78 for $0.66). On the old templates fable-medium as a second pass found 66 of 82.
- **Writers: let fable-medium write designs.** Its drafts also beat the original design in the pairwise judging (strength 4.57 against 1.38).
- **Repeat runs help only some models.** haiku-xhigh finds 58 flaws over three runs against 42 in one; sol finds the same bugs every run, and sol-high gains from repeats.
- **Cheap judges are not enough:** the writer judge was opus-high and was consistent 84-86% of the time in both orders; it also judged its own drafts, which may flatter opus-high.
- **Batch variants** (about half price, asynchronous) fit single-shot jobs only: no-tool reviews, combs with the text pasted in, grading. Squadron has no batch support.

## Costs

API-equivalent dollars on a subscription, not charges. Design review per review: hy4-flash $0.01, minimax31-flash $0.04, glm-flash $0.06, mimo $0.07, hy4 $0.19, haiku-xhigh $0.24-0.34, opus-medium $0.79, opus-high $0.96, fable-medium $2.10. Code review per review: haiku-xhigh $0.53-0.62, sonnet-high $0.52-0.57. Design writing per draft (two rounds with a haiku reviewer): haiku-xhigh $0.95, sonnet-high $1.99, opus-high $3.47, fable-medium $4.88. Comb per call: code $0.26 (opus-high), design about $1.00. Grading is about 60k tokens per case with one Sonnet agent.

From 2026-11-22. Code review per review on the public benchmark: line pass $0.01, haiku-xhigh $0.12, sol-r $0.13, the pair $0.13, fable-high $1.43. Document review per review on the current templates: haiku-xhigh $0.33, sonnet-high $0.45, opus-high $1.25, fable-high $3.06. Judging a benchmark entry costs about a cent per issue ($3.60 for the pair). Verifying 230 findings: sol-r $3.04, opus-high $9.49, fable-high $35.61.

## What we cannot say

- Who writes the best architecture document: `sq replay` has no arch phase (issue #368).
- How opus reviews code: it has only been run as a comb and a verifier. fable-high was measured on the public benchmark (RESULTS 21).
- Precision of document reviews: only recall is measured. On the current templates reviewers raise about 60% more findings, and how many of the added ones are real is not known. This is the largest open question.
- Whether an architecture review that reads little is a worse review: the key has 19 architecture flaws, 6 needing the code.
- Whether the 93 code findings that three verifiers confirmed and no golden comment matches are real: nobody has checked them by hand or against later fixes.
- How the pair scores under another judge model, or on our own code.
- Which of the 2026-11-21 template changes did the work.
- Defaults for the P4, P5 and P6 pipelines (#339): set from this data on 2026-11-17 (haiku-xhigh reviewers, fable-medium and opus-high writers); no run has compared the new defaults against the old.
- Implementation writers (the model behind P6): not measured.
- Combs on fable-medium or pooled design reviews: skipped by decision, since the haiku result gave no reason to expect a different answer.

## Limits

- Every design number rests on Sonnet-agent grades that nobody has checked by hand. A re-grade of the same reviews matched exactly (fable-medium 49 and 49; opus-high 44 and 43), so the grading is consistent; it may still be consistently wrong.
- 4 of the 43 mined cases come from response edits where the original review raised the flaws.
- One run per config for the code grids beyond grid 2, and for sonnet in design grid 2.
- The code-review comb uses run 1 of each reviewer.
- Writers: 5 and 4 slices, one judge, one fixed reviewer. Ranking fit does not converge when several writers win almost every pair; read wins and losses.
- The judge model is also a contestant, so judge self-preference may help opus-high.

## Where the data is

`review-recall-results/` holds RESULTS.md, one folder per grid (`20261112-grid2`, `20261113-grid3`, `20261113-comb`, `20261115-design`, `20261116-mined` including `grade`, `grade2`, `grade3` and `comb`, `20261117-writers`, `20261122-martian` with its own RESULTS.md, `20261122-recut`, `20261122-reading`), and the mined case files `reference/design-review-recall-cases-*.md`. Replay records are in `~/.config/squadron/runs/replay-*.json` and are not in the repository; `20261117-writers/report-2026-11-17.txt` keeps their report.
