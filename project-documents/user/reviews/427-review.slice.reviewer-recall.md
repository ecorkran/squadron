---
docType: review
layer: project
reviewType: slice
slice: reviewer-recall
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/427-slice.reviewer-recall.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: f2bf39ab0cf0c9456a30e1259b800f2e54b1e91b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
turns: 18
promptTokens: 465272
cachedTokens: 342571
cacheWriteTokens: 122691
completionTokens: 17571
durationSeconds: 175.4
costUsd: 1.402272
costBasis: provider
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Stored defect records can't reproduce the defected tree, and no step produces defected-tree line numbers"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:306-316"
  - id: F002
    severity: concern
    category: measurement-validity
    summary: "Matcher looseness is not measured, and the only control is excluded"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:204-212"
  - id: F003
    severity: concern
    category: architecture
    summary: "`latest_recall_for` on the store inverts the dependency direction"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:246"
  - id: F004
    severity: concern
    category: integration
    summary: "D8's effort check can't be done through `review_tree_diff`"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:224"
  - id: F005
    severity: concern
    category: integration
    summary: "Building into a shared set name replaces the set, which breaks the mitigation and the walkthrough"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:449"
  - id: F006
    severity: concern
    category: error-handling
    summary: "D10 leaves unpriced reviews, resumed spend and interrupted runs undefined"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:239-242"
  - id: F007
    severity: concern
    category: consistency
    summary: "Data flow disagrees with D4 on the hang rejection"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:123"
  - id: F008
    severity: note
    category: documentation
    summary: "Frontmatter and step numbering have small gaps"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:6"
  - id: F009
    severity: note
    category: error-handling
    summary: "Review hang handling is inherited, not stated"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:233"
  - id: F010
    severity: pass
    category: architecture
    summary: "Planting and ground truth align with the architecture"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#d2--defects-are-planted-by-mutation-operators-not-written"
  - id: F011
    severity: pass
    category: architecture
    summary: "Answer isolation and history-free review hold"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:467-468"
  - id: F012
    severity: pass
    category: architecture
    summary: "Measurement principles are followed"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#d7--recall-statistics"
  - id: F013
    severity: pass
    category: nfr
    summary: "Spend bound and cap are restated with concrete targets"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:237-239"
  - id: F014
    severity: pass
    category: integration
    summary: "Imports from 421, 425 and existing code match their sources"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#d9--pieces-imported-from-425"
  - id: F015
    severity: pass
    category: proportionality
    summary: "Scope is proportionate"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#technical-scope"
---

# Review: slice — slice 427

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Stored defect records can't reproduce the defected tree, and no step produces defected-tree line numbers

There are two linked gaps in the central artifact.

1. **Replay data.** The run step applies "planted edits" in a fresh sandbox (line 135), but `PlantedDefect` stores no patch and no column offsets.
   - It holds only `line_start`, `line_end`, `original` and `mutated`, in defected-tree numbering.
   - D4 requires exact segment edits, but `original` can occur twice on a line, such as a second `<` or `x + 1`.
   - A deletion records the line after the deleted text, not where to delete in the original.

2. **Line numbering.** D4 and the schema require defected-tree line numbers, but each defect is planted and verified alone, then the file is restored (line 121).
   - `call-drop`, `guard-drop` and a multi-line `return-none` all remove lines. Later defects in that file therefore have different numbers once all edits are applied.
   - No step rebases those numbers. D6 matches in a ±3 window, so an unrebased shift can silently miss a defect or credit the wrong one.

**Fix:** have the build compute the combined edit once and store it on the case, either as a patch or as original-tree spans with columns. Include it in the D5 identity. Derive each defect's `line_start` and `line_end` from the combined result, and add a test with a deletion above another defect in the same file.

### [CONCERN] Matcher looseness is not measured, and the only control is excluded

The architecture warns that "a loose matcher inflates recall". The slice plan says the matcher's looseness decides "whether the number means anything". D6 is deliberately loose:
- Any finding within ±3 lines gets credit, whatever it says.
- Any finding anchored on an enclosing function or class also gets credit, and for a class that covers every defect inside it.

A reviewer that emits many findings therefore gains recall by chance, and the paired verdict (D7) can rank it ahead for that reason alone. Showing unmatched counts beside recall doesn't quantify this. The clean-diff control is excluded (line 51), and Risk Assessment doesn't mention matcher looseness.

**Fix:** add a chance-match figure that needs no LLM spend. For example, run the existing `match` against decoy locations (unplanted mutation sites in the same case) and report the decoy hit rate per config beside recall. Add the risk to the Risk Assessment. If a decoy rate is rejected, the design should state that the chance-match rate is unmeasured and that the report says so.

### [CONCERN] `latest_recall_for` on the store inverts the dependency direction

Match results aren't stored (line 147), so returning recall and an interval means running `recall_match` and `bootstrap_mean_interval`. D11 places this on `BenchmarkRecordStore`, so `metrology/` would have to import from `benchmark/`. No module in `metrology/` imports `squadron.benchmark` today, and 421 D3 limits that store to record I/O.

Two related items are undefined:
- `RecallSummary` appears in no schema.
- D7 gives no seed for `bootstrap_mean_interval(values, seed)`, although 425 derives a seed so that reports reproduce. Without one, the report and the 425 line could print different intervals.

**Fix:** move `latest_recall_for` into `recall_report.py` on top of the store's read methods, define `RecallSummary` there, and derive the seed from the run id and reviewer key.

### [CONCERN] D8's effort check can't be done through `review_tree_diff`

D8 makes a mismatch between `ReviewResult.effort` and the resolved effort a `review_failed` absence. However, `recall_runner` reaches the reviewer only through `review_tree_diff` (line 98), and 425's `ReviewOutcome` has only `findings`, `unnormalized_count` and `cost_usd`. 425 D7 doesn't perform this check either, so the runner never sees the effort that was sent.

This matters because the architecture requires effort to be recorded as sent, and `reviewer_key` depends on it.

**Fix:** either have 427 add `effort_sent` to `ReviewOutcome`, or have `review_tree_diff` raise on a mismatch. Either way, list it as a change to 425, because line 397 currently limits changes to 425's report code to `review_flag`.

### [CONCERN] Building into a shared set name replaces the set, which breaks the mitigation and the walkthrough

421 D2's `write_case_set(name, case_ids)` writes a new version containing exactly the list it is given. The design passes it only the current build's cases (line 124), with these results:
- **Mitigation:** a build on a second cf project "into the same set name" replaces the first project's cases instead of pooling them.
- **Walkthrough:** step 2's `build --limit 1 --keep` (line 416) writes the default `recall` set with one case. Step 3 then measures only that case.

Recall sets also have no kind check on read. `recall run --set fixes` and `sq benchmark run --set recall` hit ids the other side can't load, and neither path is in a refusal list.

**Fix:** define whether a build merges with the latest version or replaces it. Pooling needs a merge, or a `--merge` flag. Give step 2 its own set name, and add a named refusal for a set of the wrong kind on the recall side. Have `write_case_set` or the set load report the kind so that 424's run can refuse too.

### [CONCERN] D10 leaves unpriced reviews, resumed spend and interrupted runs undefined

`RecallReview.cost_usd` can be `None`, but D10 doesn't say how that counts against the cap. 425 D9 counts it at the per-review figure and reports how many were unpriced. Without the same rule, a config with no reported cost could run past `--max-cost` unnoticed, which breaks the architecture's goal that spend is visible and capped.

Two other cases are also open:
- **Resumed spend:** nothing says whether spend restarts at zero on rerun. Walkthrough step 6 depends on the answer.
- **Process death:** `RecallRun.state` includes `interrupted` (line 344), but nothing says when it is set, and D10 only defines `partial`. A process killed mid-run has no stated handling. 424 does define this: a `running` record with a free lock becomes `interrupted`.

**Fix:** adopt 425 D9's unpriced rule and 424's interrupted rule by reference, state that the cap applies per invocation or per run, and reuse `BenchmarkStatus` rather than a second `Literal` of the same values.

### [CONCERN] Data flow disagrees with D4 on the hang rejection

The flow says "kept 0 → reject no_verified_defect". D4 (line 190) says a commit that ends on a hang with nothing kept is rejected as `mutant_timeout`. Rejection counts are the design's yield diagnostic, and line 393 requires a test for each reason, so implementers need one rule.

**Fix:** add the `mutant_timeout` branch to the flow.

### [NOTE] Frontmatter and step numbering have small gaps

The prerequisites name 420 (effort on the review path) and 917 (location parsers), but the `dependencies` list omits both. Development Approach also jumps from step 6 to step 8 (lines 460-461).

### [NOTE] Review hang handling is inherited, not stated

D9 cites 425 D7 for `review_failed`, and D7 covers hangs through `benchmark.review_timeout_s`, so the behavior is defined. However, 427 never mentions the timeout key. Naming it in D9 would make the review path's hang handling explicit.

### [PASS] Planting and ground truth align with the architecture

Mutation planting settles the open question in a way that fits the non-goals on curated data and per-case human review. Each defect has a location, a 402 category and a proving test that passes clean and fails with the defect. Excluding import-only failures is sound, and the report states which categories were measured.

### [PASS] Answer isolation and history-free review hold

The review runs with no tools in a history-free tree, with a fixed commit message and identity. The answers stay out of the review path, and `show` labels its output as containing them.

### [PASS] Measurement principles are followed

The case is the statistical unit, comparisons are paired, and n is shown throughout. No composite score is computed, unmatched findings aren't called false positives, and nothing gates on results. Absences follow 425's harness rule and are counted per config.

### [PASS] Spend bound and cap are restated with concrete targets

`--max-cost` is required, and the bound prints before dispatch with one review of overshoot. The cap is checked between reviews and hitting it keeps records and exits 2, matching the architecture's cost section. Unpriced reviews are the one gap, covered above.

### [PASS] Imports from 421, 425 and existing code match their sources

These imports all exist as the design describes them:
- From 425: `ReviewerRef`, `review_tree_diff`, `bootstrap_mean_interval`, `MIN_PAIRED_CASES` and `review_flag`.
- From 421: the D11 project-source rule and `FailureKind`.
- From the codebase: `location_path`, `location_span`, `ReviewCategory` and `CodeReviewFinding`.

`review_flag` is the seam 425 reserved for this slice, and 427 defines no copies.

### [PASS] Scope is proportionate

Every slice plan criterion is covered and nothing assigned to this slice is deferred. The `RecallAdapter` seam follows the architecture's per-language adapter rule, and import-closure test selection is justified by suite time. I found nothing that should be cut.

### Run Digest

- Response length: 11462 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 465272 / 342571 / 122691 / 17571 / not computed
- Duration: 175.4 s
- Cost: $1.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Responses

- **F001 (fixed):** Each defect now stores its edit in original-tree coordinates (`edit_span` plus the replacement), so no text search can pick the wrong occurrence. When the kept set is final, edits are combined per file from the last position to the first, and each defect's defected-tree lines are derived from that, so a line-removing defect shifts the ones below it. `edit_span` is part of the case identity. A planter test covers a deletion above another defect in the same file.
- **F002 (declined, recorded):** A decoy-site control adds stored decoys and a second figure to a slice already at effort 3, and decoy hits can be real issues, so the rate would be an upper bound. The design now states the chance-match rate is unmeasured, adds the risk to Risk Assessment, and the report header says so. Deferred as #300.
- **F003 (fixed):** `latest_recall_for(store, reviewer_key)` and `RecallSummary` move to `recall_report.py` on top of the store's read methods, so `metrology/` imports nothing from `benchmark/`. The interval seed is the sha256 of the run id and reviewer key.
- **F004 (fixed differently):** No mismatch check. Effort is resolved before dispatch, and 425's `review_tree_diff` passes `reviewer.effort` to the review call verbatim, so the recorded effort is the sent one by construction. No change to 425's `ReviewOutcome`.
- **F005 (fixed):** `build` writes the union of the set's latest version and the kept cases, so a rebuild leaves the version alone and a second project pools in. A set cannot shrink; a fresh start uses a new set name. Walkthrough step 2 uses `--set scratch`. `recall run` refuses a set of benchmark cases. The matching refusal in `sq benchmark run` (424) is not changed here; a recall id there fails on load.
- **F006 (fixed):** Unpriced reviews count at the per-review figure and are reported (425 D9). The cap is per invocation and `spent_usd` accumulates. Interruption follows 424's rule, and `RecallRun.state` is a `BenchmarkStatus`. 424 is now a stated prerequisite.
- **F007 (fixed):** The data flow has the `mutant_timeout` branch.
- **F008 (fixed):** `dependencies` lists 424, 420 and 917, and the step numbering is 1 to 7.
- **F009 (fixed):** D9 names `benchmark.review_timeout_s`.
