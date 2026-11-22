---
docType: reference
project: squadron
dateCreated: 20261122
dateUpdated: 20261122
status: draft
---

# Re-cut of the stored review data (2026-11-22)

No new model calls, except the amoeba 260 check. Scripts join the graded hits of `../20261116-mined/` and `../20261112-grid2/` with each review's recorded effort. Run `build.py`, `an5.py` and `b1.py` first, from a scratch directory: they write json to the working directory. Agent grades, not hand-checked. These are the assistant's findings; the Project Manager had not ruled on them.

Re-analysis on 2026-11-22 of stored artifacts only (`review-recall-results/20261116-mined`, 1281 graded design reviews, 82 flaws of which 39 are not tagged minor; and `20261112-grid2` code grades). Agent grades, not hand-checked. These are the assistant's findings; the PM had not ruled on them when this was written.

- **Reading:** flaws are tagged by what finding them needs. Doc-alone flaws: every Claude config hits 61-79%, sonnet = haiku-xhigh. Flaws needing code: sonnet 17%, opus-medium 21%, opus-high 26%, haiku-xhigh 33%, fable-medium 33%, fable-high 46%, minimax31-flash 57%. By tool calls (Claude): 0-3 calls 8%, 4-7 18%, 8-15 37%, 16-30 47%. Same model, same flaw: +12 points per doubling of tool calls on code-needing flaws, +4 on doc-alone. haiku-xhigh vs sonnet: 11 vs 2-5 tool calls, 62k vs 5-8k output tokens, 270 s vs 44-70 s. haiku does not read more than opus/fable (8-9 calls); it thinks about 7x more.
- **Price:** material flaws of 39, one run: fable-high 25 ($3.00), minimax31-flash 23 ($0.04), fable-medium 22 ($2.27), hy4 22 ($0.19), haiku-xhigh 19 ($0.24), opus-high 19 ($0.99), sonnet 18 ($0.48).
- **Sets:** haiku-xhigh + minimax31-flash + hy4 + mimo = 32/39 material (82%), 65/82 all, $0.53, about 29 CONCERN/FAIL findings per document. Picking the set on half the cases and scoring on the other half gives about 71% (58-83%) for 4, 53% for 1. 5 of 39 material flaws were found by none of the 1281 reviews.
- **Labels (design):** keeping FAIL findings only keeps 0-9 of the 18-25 material flaws a reviewer found; 74-100% of real hits are labelled CONCERN or NOTE. NOTE holds 17-25% of fable/opus hits, 3% of haiku's.
- **Labels (code grid 2):** FAIL is 87% REAL (haiku-xhigh), 94% (sol); CONCERN is 17% REAL for haiku and sonnet-high, 61% for sol. Share of REAL findings labelled FAIL: haiku 35%, sol 65%, sonnet-high 12%. MINOR titles are duplication, size guidance, stale comments, missing tests; REAL titles are behavior defects. sol: 2.4 REAL and 0.6 MINOR per review; haiku-xhigh 1.9 and 5.6.
- **Length:** hit rate on documents over 342 lines is 43% against 56-57% on shorter ones (Claude configs).

- **Sets vs repeats:** design material flaws: one reviewer 18-23, haiku-xhigh x3 28 ($0.72), 4 different cheap 31-32 ($0.53). Code grid 2 REAL issues (41 found by anyone): haiku 19, haiku x3 25, sol 25, sol x3 31, haiku + sol 33 with 8 of the 9 known bugs anyone found. Different models beat repeats; nothing is near 3x.
- **Vote filter:** design 4-set, keep items 2+ reviewers raised: 28.9 to 2.9 items per doc, key-hit share 12% to 37%, material flaws 31 to 21. Code: agreement across configs does not predict REAL (1 config 14%, 2 21%, 3 18%); haiku self-agreement does (1 run 8%, 3 runs 39%). Votes rank, they do not filter.
- **Dedupe:** different models rarely duplicate (code haiku + sol: 10.4 findings, 9.2 distinct); repeats do (haiku x3: 23.5 to 13.9). Same-file line matching merges 50% of true duplicates in code (2% wrong merges) and 31% in documents.
- **Comb by kind:** opus-high on haiku design reviews keeps 87% of key hits on slice, 79% arch, 68% tasks; material flaws 28 to 26; $1 a call. No cheap comb has been run on design reviews. Code combs are in RESULTS.md section 5 (luna-r: all real kept, 68% of noise dropped, about half a cent a call).

- **Grader checks (prompted by a second Fable's notes, 2026-11-22):** no review made zero tool calls; reviews with 2 or fewer calls got code-needing credit on 2 of 74 chances (3%). On code-needing flaws hits follow tool calls (+0.10 per doubling) and not output tokens (+0.02); on doc-alone flaws hits follow the number of findings raised (+0.13 per doubling), tool calls 0. Within haiku-xhigh, hit rate is flat across output-length thirds. The assistant read all 20 of minimax31-flash's code-needing hits: 16 clean, 3 loose, 1 a different defect, so 46-54% not 57%.
- **Ranking:** one run on 39 flaws cannot separate 25, 23 and 22; runs of one model spread about 3 (haiku 19, 18, 20; fable-medium 22, 17, 20; opus-high 19, 15, 19). The sonnet gap on code-needing flaws (17% against 46-57%) is the difference that holds.
- **Chao estimate (S + f1²/2f2) on keyed hits:** pooled over 43 docs, 4 different cheap reviewers: says 11 left, 17 truly left. Same model x3 is blind: fable-medium says 1.3 left with 27 left, opus-high 3.1 with 29. Per document it has no signal (about 2 keyed flaws per document): docs it flags have something left 1 of 3, unflagged 13 of 40. On code without a comb it inflates (haiku + sol: 359 against 221 issues).

Scripts are kept in `project-documents/user/reference/review-recall-results/20261122-recut/` (untracked when written; build.py, an1-an9, b1, b2, code1, c1-c3; run build.py, an5.py, b1.py first, from a scratch directory, since they write json to the working directory). They join `grade*/hits.json` + `map.json` with `out/*.json` metrics. Related: project-382-review-coverage, project-recipe-recall-result, project-435-436-review-shapes.

## amoeba 260 four-reviewer check

`amoeba260/`: haiku-xhigh, minimax31-flash, hy4 and mimo on amoeba slice 260's task file at amoeba `1be45d3a`, scored by one reader against the 17-item key of issue #383 (`hits.json`). 7 of 17, 8 with one borderline, for $1.73. haiku-xhigh 5, hy4 5 to 6, mimo 3, minimax31-flash 0. Six focused reviewers had found 10 of 17 for $4.21.
