---
docType: reference
project: squadron
dateCreated: 20261122
dateUpdated: 20261123
status: draft
---

# Do document reviews find more when they read the code? (2026-11-22)

The 43 mined design, task and architecture documents of `../20261116-mined/` (82 known flaws), reviewed again with the installed squadron 0.24.37 and compared with the stored reviews of the same reviewers made on 0.24.31.

Between the two versions the slice, tasks and arch templates changed (2026-11-21, #382): the documents are put in the prompt whole, the criteria say to open the code and check what the document says about it and what it would break, and the review must list what it checked in every section. Nothing else was varied here: same documents at the same commits, same reviewer aliases, same key.

## Result

Flaws found, by what finding the flaw needs (the key's `Needs:` note). 82 flaws: 35 need the code, 29 the document alone, 18 the document and its parent; 39 are not tagged minor ("material").

| Reviewer | Reviews | Need code (35) | Doc alone (29) | Doc + parent (18) | All (82) | Material (39) | Tool calls | Findings | $/review | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| haiku-xhigh | stored, run 1 | 13 | 16 | 13 | 42 | 20 | 11 | 14 | 0.23 | 266 |
| haiku-xhigh | new, run 1 | 27 | 21 | 14 | 62 | 30 | 42 | 22 | 0.33 | 454 |
| haiku-xhigh | new, run 2 | 24 | 20 | 13 | 57 | 23 | 42 | 22 | | |
| sonnet-high | stored, run 1 | 7 | 20 | 9 | 36 | 18 | 5 | 7 | 0.47 | 65 |
| sonnet-high | new, run 1 | 26 | 19 | 12 | 57 | 27 | 26 | 12 | 0.45 | 115 |
| sonnet-high | new, run 2 | 24 | 19 | 11 | 54 | 24 | 25 | 12 | | |
| opus-high | stored, run 1 | 9 | 21 | 13 | 43 | 19 | 8 | 9 | 0.94 | 100 |
| opus-high | new, run 1 | 26 | 24 | 14 | 64 | 29 | 30 | 14 | 1.25 | 187 |
| fable-high | stored, run 1 | 19 | 23 | 13 | 55 | 26 | 16 | 8 | 2.86 | 150 |
| fable-high | new, run 1 | 32 | 22 | 13 | 67 | 30 | 40 | 14 | 3.06 | 287 |

Tool calls, findings (CONCERN and FAIL), cost and seconds are medians or means per review.

- **On flaws that need the code, every reviewer about doubled or tripled:** haiku-xhigh 13 to 27 and 24 of 35, sonnet-high 7 to 26 and 24, opus-high 9 to 26, fable-high 19 to 32.
- **Flaws findable from the document alone did not move** (16 to 21, 20 to 19, 21 to 24, 23 to 22). The gain is the reading.
- **The reviewers are now close.** sonnet-high was the weakest and is within a few flaws of haiku-xhigh (57 and 54 against 62 and 57); haiku-xhigh on the current templates finds more than fable-high did on the old ones (62 and 57 against 55) at a ninth of the cost.
- **Losses are small:** stored run 1 to new run 1, haiku-xhigh gained 26 flaws and lost 6, sonnet-high 29 and 8, opus-high 23 and 2, fable-high 16 and 4.
- **Cost:** tool calls rose three to five times, cost per review rose little (haiku-xhigh $0.23 to $0.33), time about doubled. Findings raised rose about 60%; how many of the added findings are real is not measured here.
- **Run-to-run spread is still there:** haiku-xhigh's two new runs found 62 and 57 flaws, 30 and 23 material.

## Two documents no model reviewed (added 2026-11-23)

Every review of `squadron-197-tasks` and `squadron-917-tasks`, stored and new, is the task gate's own FAIL for a merge step in the task file (`model: squadron-task-gate`, `verdictSource: imposed`). No reviewer was called, so the 4 flaws of those two documents (none needs the code, all material) were never in front of a model, in either version. The scores above are in effect out of 78 flaws and 35 material for both the stored and the new rows, so the comparison between them is not affected. 12 of the 258 new reviews are these gate results; their tool calls count as 0 in the medians.

## By document kind (added 2026-11-23)

Flaws found, stored review to new reviews (flaws needing the code in parentheses), and median tool calls. `by_kind.py grade`.

| Reviewer | Arch: 19 flaws (6 need code) | Tool calls | Slice design: 32 (18) | Tool calls | Tasks: 31 (11) | Tool calls |
|---|---|---|---|---|---|---|
| haiku-xhigh | 11 (5) to 12 (3) and 12 (4) | 17 to 24 and 20 | 15 (4) to 29 (16) and 25 (12) | 10 to 44 and 50 | 16 (4) to 21 (8) and 20 (8) | 11 to 46 and 45 |
| sonnet-high | 12 (4) to 11 (2) and 10 (2) | 6 to 6 and 5 | 14 (2) to 26 (15) and 26 (15) | 4 to 27 and 28 | 10 (1) to 20 (9) and 18 (7) | 4 to 29 and 26 |
| opus-high | 13 (3) to 14 (3) | 12 to 20 | 13 (3) to 30 (16) | 8 to 33 | 17 (3) to 20 (7) | 7 to 36 |
| fable-high | 15 (5) to 15 (6) | 24 to 30 | 18 (6) to 30 (17) | 14 to 40 | 22 (8) to 22 (9) | 18 to 51 |

- **The gain is in slice designs and task files.** On slice designs every reviewer went from 13-18 of 32 to 25-30. Architecture reviews did not move for any reviewer.
- **Architecture reviews read less, and sonnet-high barely reads there** (5 to 6 tool calls, unchanged from the stored run, against 20 to 30 for the others).
- **Reading little did not cost architecture reviews anything against this key.** The new architecture reviews with 3 or fewer tool calls (8 reviews, all sonnet-high) found 10 of the 16 flaws in their documents (62%); those with 11 or more found 53 of 78 (68%). 13 of the 19 architecture flaws are in the document or its parent. On the 6 that need the code: fable-high 6, haiku-xhigh 3 and 4, opus-high 3, sonnet-high 2 and 2.
- **No slice-design or task review that called a model made fewer than 4 tool calls.** The reviews with 3 or fewer calls are the 12 gate results above and the 8 sonnet-high architecture reviews.
- The architecture key is 9 documents and 19 flaws, 6 needing the code. It cannot say whether an architecture review that reads little is a worse review.

## Sets of the new reviews (added 2026-11-23)

Unions of run-1 reviews over the 78 flaws a model saw (35 need the code). Cost is the sum of the reviews' costs. In-sample, one run each.

| Set | Flaws of 78 | Need code, of 35 | Cost a document |
|---|---|---|---|
| haiku-xhigh | 62 | 27 | $0.33 |
| sonnet-high | 57 | 26 | $0.45 |
| opus-high | 64 | 26 | $1.25 |
| fable-high | 67 | 32 | $3.06 |
| haiku-xhigh, both runs | 68 | 30 | $0.66 |
| haiku-xhigh + sonnet-high | 67 | 28 | $0.78 |
| haiku-xhigh + opus-high | 69 | 30 | $1.58 |
| haiku-xhigh + fable-high | 72 | 33 | $3.39 |
| all four | 74 | 33 | $5.09 |

Two haiku-xhigh runs find as many keyed flaws as one fable-high review. A set raises the sum of its members' findings (haiku-xhigh 22 a review, sonnet-high 12, opus-high and fable-high 14), and how many of those are real is not measured.

## Limits

- One stored run against one or two new runs per reviewer. The differences above are far larger than the spread between the new runs, except where noted.
- The comparison is two squadron versions, so every template change between them is in it together; it does not say which change did the work.
- Agent grades (blind, one Opus grader per pile, brief in `grade/BRIEF.md`), not hand-checked. Old and new reviews were graded in the same anonymous pile. The stored reviews' new grades match their 2026-11-16 grades: 169 flaw hits agree, 2 were dropped and 7 added.
- The key is the 82 flaws someone found and wrote down, so it says nothing about findings outside it.

## Files

- `prepare.py WORK_DIR`: rebuilds the 43 case trees outside the repository. `run.sh WORK_DIR CASE ALIAS N`: one review. `jobs.txt`: the 258 reviews run (`xargs -P 6 -L 1 ./run.sh WORK_DIR < jobs.txt`). Outputs in `out/`.
- `prepare_grade.py PILE_DIR`: the blind piles (six new reviews and four stored ones per case, shuffled); `map.json` says which is which. `grade/`: the graded piles. `score.py grade`: the Result table. `by_kind.py grade`: the tables by document kind, the gate results, the reviews by tool calls and the sets.
- Cost: $252 at list price, all on the Claude plan; grading by 18 subagents.
