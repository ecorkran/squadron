---
docType: review
layer: project
reviewType: slice
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 11bdfb072962618a866454c5d418413ecf3a3ac2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
effort: xhigh
turns: 15
promptTokens: 586456
cachedTokens: 479771
cacheWriteTokens: 106669
completionTokens: 49757
durationSeconds: 233.8
costUsd: 0.108124
costBasis: provider
runId: run-20261116-p4-de696884
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: scope
    summary: "Sandbox extension reopens the replay stack the parent froze"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:230"
  - id: F002
    severity: fail
    category: validity
    summary: "Reviewer recall does not keep the later fix out of reach"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:233"
  - id: F003
    severity: concern
    category: scope
    summary: "Pool semantics differ from the plan and contradict the recipe comment"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:172-177"
  - id: F004
    severity: concern
    category: integration
    summary: "The report omits the matched-nothing count the parent names"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:298-310"
  - id: F005
    severity: concern
    category: data-model
    summary: "Identity omits two parent-required fields and takes effort from the alias"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:202"
  - id: F006
    severity: concern
    category: data-model
    summary: "Case identity leaves out the frozen bug-file list"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:140-141"
  - id: F007
    severity: concern
    category: data-model
    summary: "Per-finding label records run against the coarse-record rule"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:219, :261-264"
  - id: F008
    severity: concern
    category: error-handling
    summary: "Failure modes are enumerated for review calls only"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:235-240"
  - id: F009
    severity: concern
    category: proportionality
    summary: "The design is heavier than its slice; cut or defer these"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md#technical-decisions"
  - id: F010
    severity: concern
    category: validity
    summary: "Reported comparisons carry no uncertainty"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:305-307"
  - id: F011
    severity: note
    category: scope
    summary: "The production-path refactor is not in the plan entry"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:223-226"
  - id: F012
    severity: pass
    category: integration
    summary: "Interfaces and dependencies exist as the design describes"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:77-80"
  - id: F013
    severity: pass
    category: scope
    summary: "Live-run case set follows the measurement rule"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:268-271"
---

# Review: slice — slice 430

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Sandbox extension reopens the replay stack the parent froze

D7 adds a `history_from` parameter to 421's `HistoryFreeSandbox`. The architecture amendment (`420-arch`, "Amendment (20261115)") says the implementation replay stack "stays, with no further work on it", and the slice plan says 421–426 "stay as built and get no further work". The design's own Technical Scope excludes "any change to the replay stack (421–426)" (line 66), and D7 contradicts that line. The fetch-depth rule itself is sound: every commit on a path from `head` to `base` lies in `base..head`, so `count + 1` always reaches `base`. Fix: leave 421 untouched and have `recall/` own a wrapper that calls `HistoryFreeSandbox` and does the deeper fetch, or get an explicit PM amendment for this one change.

### [FAIL] Reviewer recall does not keep the later fix out of reach

The plan requires reviewers to run "with tools, in 421's history-free sandbox at `head`, so the later fix cannot be read." D7 leaves the tools unconfined, so a reviewer's `read_file` or `grep` can reach the source checkout named in each case, which holds the fix once it is merged. The design says nothing scans for such reads and labels the result "no leak detected" only in that sense. The parent's principle is stronger: "leakage is this component's problem" and "a run that reaches for it is not graded" (`420-arch`, Architectural Principles). Grading (D5) runs the same tools at `head`, so it has the same exposure. The grids finding no such reads is not a scan. Fix: apply the 424 transcript leak scan to review and grade calls and exclude runs that trip it, or confine the review tools to the sandbox. If the PM accepts a weaker guarantee, amend the plan line and the architecture principle first.

### [CONCERN] Pool semantics differ from the plan and contradict the recipe comment

The plan entry for 430 says "an optional pool to pick from at random." D2 instead scores a pool as the mean of all members and runs every member. The recipe example on line 172 says "true = one member per case run", which is the random-pick reading, and line 177 describes the all-members mean. These are different measurements with different costs (N calls per run instead of one). The success criterion on line 347 follows the all-members version, so line 172 is the stray text. Decide one reading, record it as a decision, and state the cost consequence.

### [CONCERN] The report omits the matched-nothing count the parent names

The parent's Reviewer recall section says findings are matched to known bugs "to give recall, plus the count of findings that matched nothing" (`420-arch`, Reviewer recall). The report table has "Findings/run" (all findings) and "Undecided" but no count of findings that matched no bug. D3's decided-miss rule already determines this count. Add a per-recipe column for findings with no hit for any bug. Define it so that undecided candidates are not counted there, and so that pruning (line 191) does not change it.

### [CONCERN] Identity omits two parent-required fields and takes effort from the alias

The parent requires a result to name "the alias's `tool_use` and `max_output_tokens`" so reports compare only matching results (`420-arch`, Design Goals). `ReviewerRef` in D4 carries neither. Its `reviewer_key` is derived from model, profile, effort and template hash only, which I checked in the code.

Line 259 also takes imported reviewer `effort` from the output's own `effort` field. I checked a hand-run output (`grid2`, haiku-xhigh run 1): it has `"effort": "xhigh"` and no `effort_sent`. For imports, identity therefore holds the alias's value, which the 420 slice forbids as a stand-in for effort sent. The design never says what `effort_sent` is for an imported stage. Fix: state that imported `effort_sent` is null, add `tool_use` and `max_output_tokens` to the reviewer identity, and have the report flag mismatched identities instead of merging them. If the import copies `effort` into `effort_sent`, raise this to FAIL.

### [CONCERN] Case identity leaves out the frozen bug-file list

The case id hashes `(kind, repo name, base, head, bugs)`. Bug files derived from proof commits are "frozen into the record when the case is added" (line 141), but they are not part of the id. Re-adding a case after the derivation changes gives the same id with different content, and the write-once store then either rejects it or keeps the old version silently. The 421 criterion says changing any part of a case's content identity produces a new case id, and `420-arch` says "changing any of those makes a new case." Fix: hash the resolved locations into the id, or hash the derivation inputs.

### [CONCERN] Per-finding label records run against the coarse-record rule

The parent says "records stay coarse, one per case run, because the store reads every file on every query" (`420-arch`, Architectural Principles). D5 writes one grade label per finding, D10 writes one label per member of each graded issue, and hit labels are per finding × bug. The import alone covers about 700 review outputs (line 38), each with several findings, so it writes thousands of label records. The design never counts them. Fix: count the import's records in the design, then store labels per stage or per case as one record holding a map keyed by content key (line 190 already makes that key available). Or justify per-finding files with a measured query cost.

### [CONCERN] Failure modes are enumerated for review calls only

D8 covers reviewer crash, timeout and unparseable output, and harness failures for repo, sandbox and base. It does not cover the same modes for:
- **Comb calls.** A crashed or timed-out comb has no defined outcome. Under D8 a comb with no parseable output would read as `UNDECIDED` for every finding, which is a scored result, not a config failure.
- **Grade calls (D5).** A grader that times out, or returns some finding lines and not others, has no rule. D5 says a graded finding is never graded again, so a missing grade could be permanent or retried, and the design doesn't say which.
- **The deeper fetch (D7).** A stalled fetch has no timeout, and a dropped connection mid-fetch has no stated outcome.
- **Per-call timeouts.** None is specified for the new calls.

The review rule requires each mode to be observable (WARNING or above, or a metric) and each to have a test asserting the signal. The Testing paragraph (line 445) lists no test for config failure or for comb and grade timeouts. Fix: add rows to D8, take the timeout from configuration, and add a test per mode.

### [CONCERN] The design is heavier than its slice; cut or defer these

The plan rates 430 at 3/5 effort and Medium risk. The design has eleven decisions, thirteen modules plus a CLI and two templates (lines 88–106), and several mechanisms the plan does not ask for. Cut or defer:
- **32 KiB truncation (line 213).** The design's own largest review is about 15 KB, so no case here needs it. Truncating descriptions also changes the text that comb and label read. Store the full output inline, or fail loudly when a record is over the cap.
- **Pruning of undecided candidates (line 191).** It only shortens a listing, and it makes "undecided" counts depend on what was listed. Drop it.
- **Recipe identity hash (line 178).** No record key, stage id or report column uses it: stage ids come from `reviewer_key` and the input stage, and reports show the recipe name. Either name where it is stored or remove it.

### [CONCERN] Reported comparisons carry no uncertainty

The parent's Breakdown principle says results are reported "with n and paired intervals," and it lists review findings among the measures (`420-arch`, Architectural Principles). The report shows bug-hits as raw fractions (16/42 against 12/42) with no interval. Its job is to answer whether a replacement is "better or worse" (line 42), and small differences on 10 cases can be noise. Add a paired case-level interval for recall and for findings per recipe, or show "not distinguishable" when the interval spans zero.

### [NOTE] The production-path refactor is not in the plan entry

D6 moves input assembly out of `sq review code`, which touches a production command that the plan entry for 430 does not mention. The change follows the parent's "replays run the production pipelines" principle, and line 358 requires the existing `sq review code` tests to pass unmodified. Name it in the plan entry so the scope is recorded.

### [PASS] Interfaces and dependencies exist as the design describes

I checked these symbols in the source: `HistoryFreeSandbox`, `GradeCapReached`, `ReviewBudget`, `EXIT_CAP_REACHED` (in both `benchmark_grade` and `diff_judge_runner`), `ReviewerRef`, `reviewer_key`, `run_review_with_profile`, `TemplateOutput.DECISIONS`, `template_content_hash`, `map_historical_category`, `CodeReviewFinding`, `sweep_benchmark_orphans`, `ContentSidecars`, and `review_tree_diff`. I could not verify `bench_lock`, which had no definition in the metrology package. The frontmatter dependencies (421, 425, 402) and interfaces (432, 433) match the plan entry.

### [PASS] Live-run case set follows the measurement rule

The case roster checks out: 17 cases, three from squadron's own repo (932, 175, 197), so 14 non-squadron, as D11 states. Running D11 on `real-bugs-nonsquadron` follows the "no task runs against squadron's own history" rule. Batch-2 cases do have `haiku-xhigh-1` and `sol-1` runs in `grid3`, so the "most reviews already exist" claim holds. The cases file's line that batch 2 is "not yet in any grid" is stale, and the design does not depend on it.

### Run Digest

- Response length: 12784 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 586456 / 479771 / 106669 / 49757 / not computed
- Duration: 233.8 s
- Cost: $0.11 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
