---
docType: review
layer: project
reviewType: slice
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: c2f2c487f338607cc4eb8e4369f0ccfd8664c409
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
effort: xhigh
turns: 34
promptTokens: 1266080
cachedTokens: 1111869
cacheWriteTokens: 154185
completionTokens: 85030
durationSeconds: 393.9
costUsd: 0.275386
costBasis: provider
runId: run-20261116-p4-de696884
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: data-integrity
    summary: "Imported stages have no source for template hash or comb configuration"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:291"
  - id: F002
    severity: concern
    category: data-integrity
    summary: "Imported grades come from three layered passes with no grader identity"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:297"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Case, bug and control counts do not reconcile with the case file"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:422"
  - id: F004
    severity: concern
    category: scoring-validity
    summary: "Undecided candidates count as misses, which biases recall comparisons"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:200"
  - id: F005
    severity: concern
    category: security
    summary: "The leak rules are narrower than the architecture's named leak paths"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:242"
  - id: F006
    severity: concern
    category: integration
    summary: "The `sq` subprocess is called by bare name in an environment that does not put it on PATH"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:240"
  - id: F007
    severity: concern
    category: scope
    summary: "Concurrency (`--jobs`) goes against the architecture's non-goal and is not in the plan"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:281"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Proportionality: the location derivation can be cut"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:151"
  - id: F009
    severity: concern
    category: architecture-alignment
    summary: "Each stage call is stored as a record, against the coarse-record rule the design says it follows"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:227"
  - id: F010
    severity: concern
    category: architecture-alignment
    summary: "Stage records do not reference the case set version"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:209"
  - id: F011
    severity: concern
    category: store-semantics
    summary: "Records are \"write-once,\" but retry deletes them"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:271"
  - id: F012
    severity: note
    category: architecture-alignment
    summary: "Recall's sandbox is not one commit"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:249"
  - id: F013
    severity: note
    category: traceability
    summary: "Dependency lists disagree across the plan, the frontmatter and the body"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:6"
  - id: F014
    severity: pass
    category: architecture-alignment
    summary: "The core architecture rules are carried into the design"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md#technical-decisions"
---

# Review: slice — slice 430

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Imported stages have no source for template hash or comb configuration

D10 takes imported stage config from each output's own fields and sets the template hash to "that of the template current then." Neither source works. Review outputs record `template_name` ("code") but no hash. The existing `template_content_hash` takes a template name and returns the hash of the template as it stands now, so it cannot recover a historical hash. `ReviewerRef.template_hash` is a required string, so the rule "store missing fields as null" cannot apply to it. The design never says where a historical hash would come from.

Comb outputs are worse. The sampled comb output has `effort` null, `recovery_turn_used: true`, and no `model`, `profile`, `template_name` or `max_output_tokens` at all. The comb alias can only come from the folder name (`out/<comb>/`), which D10 never uses. Under D10's rules, imported combs cannot get `model` or `profile`. The recovery turn they used is also not the `decisions` behavior the live comb will have (D6, line 86), so they may not be the same config.

Fix: name the source of every imported identity field. Use an explicit unknown marker, not a current-template hash, where the source is missing. State how a comb folder maps to model and profile.

### [CONCERN] Imported grades come from three layered passes with no grader identity

D10 reads `*-graded*.json` and puts the grades in "one import label record per case." Each case has up to three grade files: `{case}-graded.json`, `{case}-graded-b2.json` and `{case}-graded-sol.json`. They are separate agent passes with their own briefs and their own issue id spaces (I#, M#, N#, S#). The scoring script reads them in sequence because later files add to earlier ones.

The design does not say how the layers combine, how a grader's `matched` reference maps to a finding's content key, or which pass wins on disagreement. D5 requires the report to show the grader key beside graded-real share, but the import record has no grader key, so imported shares cannot be labelled.

Fix: give each grading pass its own grader identity and labeler record, as D5 already defines for agent grades. State the merge rule for the case where two passes grade the same finding.

### [CONCERN] Case, bug and control counts do not reconcile with the case file

The design expects 17 cases, 21 bugs and 3 controls (lines 386, 422, 429). The case file does not support those numbers as written.

- Its batch 2 section lists eight bugs across seven cases. `context-forge-9006d54c` lists a second bug (`cf9006d5-N1`). Its totals say "one bug each," which gives 21 total; the bullets give 22.
- D1 defines `control` as "the saved review reported it." Six batch 2 bugs are marked as reported by the saved review, so D1 would make them controls, not three. The three controls the case file names (two on amoeba-122, one on trading-ui-103) are not B-numbered and have no place in D1's schema.
- The success criteria require the `real-bugs-original-no-u103` set (line 388), but the walkthrough never creates it. Line 422 lists only the original-10 and non-squadron sets.
- The report example (line 342) titles a 10-case report "real-bugs v1," which contradicts 17 cases.
- I could not reproduce the 723 review-output count on line 429 with the file listing available. The 480 comb count matches.

Fix: the PM decides whether the second `cf9006d5` bug counts, and whether a bug the saved review reported is a scored bug or a control. Then make D1, the expected counts and the walkthrough agree with that decision.

### [CONCERN] Undecided candidates count as misses, which biases recall comparisons

D3 says an unlabelled candidate is "never counted." In the recall formula that means it counts as not a hit. D12 then pairs recipes on that recall with no adjustment. A recipe that produced more unlabelled candidates looks worse, and the paired interval does not reflect that. The matched-nothing rule (line 201) has the opposite asymmetry: undecided findings are excluded from it. The architecture says absent is not zero (architecture line 71). A missing decision should not score as the negative.

Fix: report recall as a lower and an upper bound, counting undecided candidates first as misses and then as hits. Compute paired intervals only over (case, run) pairs with no undecided candidate in either recipe, and print how many pairs were excluded. The undecided column already exists, so this changes what the comparison uses.

### [CONCERN] The leak rules are narrower than the architecture's named leak paths

The architecture requires the transcript scan to check reads of the user's checkout, installed site-packages, the package manager's cache and the store (architecture line 50). D6's protected roots are the case repo, the real home, the store and the squadron checkout. Site-packages and the package cache are missing. The 424 leak-rule builder also takes install location, package cache, distribution name, and host owner and repo as inputs. D6 does not say what recall passes for any of them.

Recall reviews have no install step. An installed copy of `sq` can still carry a later squadron version, which is the case the architecture names.

Fix: list the full protected set in D6. State the builder inputs for recall, including the host repo that the git rule checks.

### [CONCERN] The `sq` subprocess is called by bare name in an environment that does not put it on PATH

D6 runs `sq review code` and `sq benchmark recall _stage` as subprocesses in 421's scrubbed environment. That environment's PATH holds only the home bin and the system directories, and only git and uv are linked into it. 421's auth check and slice runner avoid this by passing an absolute `sq` path, resolved once by `resolve_sq_path()`. The design does not say to do the same, so the review call fails with "sq not found" wherever `sq` is installed outside the system directories.

Fix: state that both subprocess calls use the path from `resolve_sq_path()`, as 421 does.

### [CONCERN] Concurrency (`--jobs`) goes against the architecture's non-goal and is not in the plan

The architecture's non-goals say "No concurrent replays. Configs and samples run one after another ... (#146 covers concurrency)" (architecture line 156). Future work item 3 is the same concurrency under #146. D9 argues the non-goal covers replays and not reviews. But the non-goal's own wording is about configs and samples, and recall's stages are configs and samples. The plan entry for 430 has no concurrency either.

The cost is real: an asyncio semaphore, comb stages that wait on their inputs, and a cap check that can overshoot by N−1 per-call bounds. Each needs its own tests.

Fix: run serially in this slice and defer `--jobs` to #146. If the PM wants it now, that is a decision to make against the architecture non-goal first.

### [CONCERN] Proportionality: the location derivation can be cut

When a case does not list its bug files, D1 derives them from the proof commits, excludes test files by heuristic, and freezes the result into the case id. That adds git reads at `cases add`, a heuristic that can be wrong, and a dependency of the content id on git output. This slice writes all 17 case files itself, so every file the case needs can be listed explicitly. The file the design cites as the reason (`cutover_304_first_purchase.py`) is one the YAML can name directly.

Fix: make `locations` required and fail validation when it is absent. Cut the derivation and its heuristic. This is the heavier option where a lighter one meets the requirement, which the project's rule against added complexity disallows.

### [CONCERN] Each stage call is stored as a record, against the coarse-record rule the design says it follows

D4 says the design writes "one record per case run, as the architecture's coarse-record rule asks." The architecture's rule is one record per case run, because the store reads every file on every query (architecture line 69). The design writes one record per call, so a reviewer's review and each of its combs are separate records. Its own numbers show this: 1,203 records for the import (723 reviews and 480 combs), more than the reviews alone.

Fix: either pack a reviewer's review and its combs into one record per (case, run, reviewer), keeping each comb addressable for reuse, or state the deviation and its reason. Do not leave the compliance claim as it is.

### [CONCERN] Stage records do not reference the case set version

The architecture requires every result to reference "the case and the set version it was run under" (architecture line 67). `RecallStage` has `case_id` and `run_index` but no set reference. The set version appears only in the report header, which comes from the command. A stored result cannot be traced to the set it was produced for. Case ids are content-based, so each case is pinned; the set is not.

Fix: record the set name and version with each stage, or with a run record that lists the stage ids it produced. State which one the report reads.

### [CONCERN] Records are "write-once," but retry deletes them

D4 says "Records are write-once" (line 226). D8 says `run --retry-harness` deletes harness-failure and dropped-leak records first (line 271). The design does not say whether the store supports deletion, and it does not say how the report treats a retried stage.

Fix: choose one rule. If deletion is allowed, name the store operation. If records are write-once, make retry write a superseding record and state that the report uses the newest.

### [NOTE] Recall's sandbox is not one commit

The architecture describes the history-free sandbox as one commit with no refs to later history (architecture line 50), and the plan entry says "at `head`." D7 adds ancestry from head back to base, so the production `--diff base` call can run. The leak property holds, because an ancestry fetch cannot reach a later commit. Record this as a deliberate extension in the design, and either amend the architecture's wording or note that "one commit" describes replays only. That keeps the name "history-free" accurate for later readers.

### [NOTE] Dependency lists disagree across the plan, the frontmatter and the body

The plan entry lists [421, 425] and 402. The design's frontmatter lists 421, 424, 425 and 402, and leaves out 420, although the body relies on 420 (effort sent, line 80) and on 424 (leak scan, D6). The additions are needed. Update the plan entry to include 420 and 424, and add 420 to the frontmatter.

### [PASS] The core architecture rules are carried into the design

Checked against the architecture and the current code:
- The `sq review code` options D6 relies on exist (`--no-save`, `--output`, `--output-path`).
- `DECISIONS`, `ReviewBudget`, `EXIT_CAP_REACHED`, `compare_pair`, `pair_seed`, `transcript_source_for`, `leak_scan.scan`, `map_historical_category` and `template_content_hash` all exist under the names the design cites.
- D9 restates the cost bound and cap, as the architecture's spend rule requires.
- D8 counts config failures as misses and drops harness and leak failures, which matches the absent-is-not-zero rule.
- D4 keeps `effort_sent` as recorded and shows null as "not recorded."
- D12 computes no composite score.
- The first live recipe runs on non-squadron cases, as the measurement rule requires.

### Run Digest

- Response length: 13731 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 34
- Tokens — prompt / cached / cache write / completion / reasoning: 1266080 / 1111869 / 154185 / 85030 / not computed
- Duration: 393.9 s
- Cost: $0.28 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
