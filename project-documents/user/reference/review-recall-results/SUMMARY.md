---
docType: reference
project: squadron
dateCreated: 20261117
dateUpdated: 20261117
status: draft
---

# Model benchmark: what we measured and what it says

The short version of [RESULTS.md](RESULTS.md) (18 sections of tables) for a person. The same answers in a form an agent can look up: [ANSWERS.yaml](ANSWERS.yaml). Where the two disagree, RESULTS.md and the data files are the source.

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

A design flaw counts only if the document contradicts itself, its parent or the code, omits a success criterion, or has a task that cannot be done as written. Later decisions and scope changes never count. Flaws were mined from review history and checked against the text at that commit.

## Answers

Confidence is about the evidence, not the model.

| Question | Answer | Confidence |
|---|---|---|
| Worst reviewer | Sonnet at any effort. About 40% recall against 47-57% for the other Claude configs; on task breakdowns 9-10 of 31 flaws against 17-21. Also last in the code grid. | High |
| Best design reviewer for the money | haiku-xhigh: $0.34 a review, ties the dearer configs on recall (43.7 flaws per run of 82, fable-medium 46.3, opus-high 42.7, opus-medium 38.7). | High on value; medium on who is top, because the top three are inside the 3-6 flaw run-to-run spread |
| Design review against code review | haiku-xhigh leads both. The rest differs: sol (Codex) found 12 of 42 known bugs at 79% precision on code, and 2 of 25 flaws on design. | Medium (sol design: 9 cases, one run) |
| Combs | Code: the opus-high comb keeps 91% of real findings and all known bugs, and cuts noise by 93%. Design: it keeps 78% of real findings, loses 7 of 58 distinct flaws, and costs three times the review. | Design medium-high; code medium (one run, 10 cases) |
| Two reviewers | fable-medium plus haiku-xhigh find 66 of 82 flaws; haiku-xhigh alone, over three runs, 58. On code, haiku-xhigh plus sol cover 8 of 14 known bugs, more than either alone. | Medium |
| Best writer | Designs: fable-medium (14 wins, 2 losses, 3 ties), then opus-high. Tasks: opus-high or fable-medium. haiku-xhigh and sonnet-high write poor designs and lose to the original. | Medium for design; low for tasks (4 slices, thin fable sample) |
| Effort | Opus: high beats medium (42.7 against 38.7). Sonnet: no effect. Fable: high 52, medium 49 on one run, inside noise. | Medium for opus, low for fable |
| Hardest case kind | Slice designs: 25 of 32 flaws found by anyone. Arch 18 of 19, tasks 25 of 31. 14 of 82 flaws were found by nobody. | Medium |

## Recipes worth keeping

Ideas that came out of the data, so they are not lost:

- **Code review: haiku-xhigh and sol in parallel, then an opus-high comb.** On the 10 original cases (one run): the raw union is 104 findings holding 33 distinct real issues and 8 of 14 known bugs. After the comb: 45 findings, 30 real issues, all 8 known bugs. The comb cut 57% of the findings and lost 3 of 33 real issues. This is the recipe slice 430 commits as the first one. A luna comb in place of opus-high keeps everything but leaves 65 findings, nearly all the noise.
- **Two-stage comb on code (luna-r, then opus-high):** 89% precision, 12 of 14 known bugs kept. The recorded cost is higher than opus-high alone and is unexplained; do not rely on it.
- **Design review: haiku-xhigh by default, fable-medium as a second pass, no comb.** The pair finds 66 of 82 flaws.
- **Writers: let fable-medium write designs.** Its drafts also beat the original design in the pairwise judging (strength 4.57 against 1.38).
- **Repeat runs help only some models.** haiku-xhigh finds 58 flaws over three runs against 42 in one; sol finds the same bugs every run, and sol-high gains from repeats.
- **Cheap judges are not enough:** the writer judge was opus-high and was consistent 84-86% of the time in both orders; it also judged its own drafts, which may flatter opus-high.
- **Batch variants** (about half price, asynchronous) fit single-shot jobs only: no-tool reviews, combs with the text pasted in, grading. Squadron has no batch support.

## Costs

API-equivalent dollars on a subscription, not charges. Design review per review: haiku-xhigh $0.34, opus-medium $0.79, opus-high $0.96, fable-medium $2.10. Code review per review: haiku-xhigh $0.53-0.62, sonnet-high $0.52-0.57. Design writing per draft (two rounds with a haiku reviewer): haiku-xhigh $0.95, sonnet-high $1.99, opus-high $3.47, fable-medium $4.88. Comb per call: code $0.26 (opus-high), design about $1.00. Grading is about 60k tokens per case with one Sonnet agent.

## What we cannot say

- Who writes the best architecture document: `sq replay` has no arch phase (issue #368).
- How fable and opus review code: the code grids did not include them.
- Precision of design reviews: only recall was measured; noise is seen only through the comb.
- Defaults for the P4, P5 and P6 pipelines (#339): the data now supports a recommendation, but nobody has compared defaults.
- Combs on fable-medium or pooled design reviews: skipped by decision, since the haiku result gave no reason to expect a different answer.

## Limits

- Every design number rests on Sonnet-agent grades that nobody has checked by hand. A re-grade of the same reviews matched exactly (fable-medium 49 and 49; opus-high 44 and 43), so the grading is consistent; it may still be consistently wrong.
- 4 of the 43 mined cases come from response edits where the original review raised the flaws.
- One run per config for the code grids beyond grid 2, and for sonnet in design grid 2.
- The code-review comb uses run 1 of each reviewer.
- Writers: 5 and 4 slices, one judge, one fixed reviewer. Ranking fit does not converge when several writers win almost every pair; read wins and losses.
- The judge model is also a contestant, so judge self-preference may help opus-high.

## Where the data is

`review-recall-results/` holds RESULTS.md, one folder per grid (`20261112-grid2`, `20261113-grid3`, `20261113-comb`, `20261115-design`, `20261116-mined` including `grade`, `grade2`, `grade3` and `comb`, `20261117-writers`), and the mined case files `reference/design-review-recall-cases-*.md`. Replay records are in `~/.config/squadron/runs/replay-*.json` and are not in the repository; `20261117-writers/report-2026-11-17.txt` keeps their report.
